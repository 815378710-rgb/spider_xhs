// 小红书 Cookie 采集器 - popup.js (v1.1.2)
const DEFAULT_SERVER = 'http://192.168.68.162:5000';
let serverUrl = '';

// ── 初始化 ──
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const data = await chrome.storage.local.get('serverUrl');
        serverUrl = data.serverUrl || DEFAULT_SERVER;
    } catch (e) {
        console.warn('storage not available, using default:', e);
        serverUrl = DEFAULT_SERVER;
    }

    document.getElementById('serverUrl').value = serverUrl;
    if (!document.getElementById('serverUrl').value) {
        document.getElementById('serverUrl').value = DEFAULT_SERVER;
        serverUrl = DEFAULT_SERVER;
        try { chrome.storage.local.set({ serverUrl: DEFAULT_SERVER }); } catch (e) {}
    }

    checkXhsStatus();
    checkServerStatus();
    loadProxyState();
    // 通知 background 更新 serverUrl
    try { chrome.runtime.sendMessage({ type: 'SET_SERVER_URL', url: serverUrl }); } catch (e) {}
});

// ── 保存服务端地址 ──
function saveServerUrl() {
    const url = document.getElementById('serverUrl').value.trim().replace(/\/+$/, '');
    if (!url) { showMsg('error', '请输入服务端地址'); return; }
    serverUrl = url;
    try { chrome.storage.local.set({ serverUrl: url }); } catch (e) {}
    showMsg('success', '✅ 服务端地址已保存');
    checkServerStatus();
}

// ── 检测小红书状态 ──
async function checkXhsStatus() {
    const dot = document.getElementById('dot-xhs');
    const status = document.getElementById('status-xhs');
    const btn = document.getElementById('btnCollect');

    // 检查 chrome.cookies API 是否可用
    if (typeof chrome === 'undefined' || !chrome.cookies) {
        dot.className = 'status-dot dot-red';
        status.textContent = '❌ chrome.cookies 不可用，请重新安装插件';
        btn.disabled = true;
        return;
    }

    try {
        // 尝试多种域名匹配
        const cookies1 = await chrome.cookies.getAll({ domain: '.xiaohongshu.com' });
        const cookies2 = await chrome.cookies.getAll({ domain: 'xiaohongshu.com' });
        const cookies3 = await chrome.cookies.getAll({ domain: '.www.xiaohongshu.com' });

        // 合并去重（按 name 去重，保留第一个）
        const seen = new Set();
        const allCookies = [];
        for (const c of [...cookies1, ...cookies2, ...cookies3]) {
            if (!seen.has(c.name)) {
                seen.add(c.name);
                allCookies.push(c);
            }
        }

        const hasA1 = allCookies.some(c => c.name === 'a1');
        const hasWebSession = allCookies.some(c => c.name === 'web_session');

        // 收集所有 cookie 名用于调试
        const cookieNames = allCookies.map(c => c.name).join(', ');
        console.log('[Cookie采集器] found cookies:', cookieNames);

        if (allCookies.length > 0 && hasA1) {
            dot.className = 'status-dot dot-green';
            status.textContent = `✅ 已登录 (${allCookies.length} 条cookie${hasWebSession ? '，含web_session' : ''})`;
            btn.disabled = false;
        } else if (allCookies.length > 0) {
            dot.className = 'status-dot dot-yellow';
            status.textContent = `⚠️ 有 ${allCookies.length} 条cookie 但缺 a1`;
            btn.disabled = false;
        } else {
            // 显示更详细的调试信息
            const domains = ['.xiaohongshu.com', 'xiaohongshu.com', '.www.xiaohongshu.com'];
            const counts = [cookies1.length, cookies2.length, cookies3.length];
            dot.className = 'status-dot dot-red';
            status.textContent = `❌ 未找到小红书cookie (检测了3个域名，均为空)`;
            btn.disabled = true;

            // 同时尝试不限域名获取所有 cookie 中包含 xiaohongshu 的
            try {
                const allSiteCookies = await chrome.cookies.getAll({});
                const xhsRelated = allSiteCookies.filter(c =>
                    c.domain && c.domain.includes('xiaohongshu')
                );
                if (xhsRelated.length > 0) {
                    const info = xhsRelated.map(c => `${c.domain}:${c.name}`).join(', ');
                    status.textContent = `❌ 未找到cookie (但发现 ${xhsRelated.length} 条相关: ${info})`;
                    console.log('[Cookie采集器] xhs related cookies found via getAll({}):', info);
                }
            } catch (e2) {
                console.log('[Cookie采集器] getAll({}) failed:', e2);
            }
        }
    } catch (e) {
        console.error('checkXhsStatus error:', e);
        dot.className = 'status-dot dot-red';
        status.textContent = '❌ 检测出错: ' + (e.message || e.toString());
        btn.disabled = true;
    }
}

// ── 检测服务端状态 ──
async function checkServerStatus() {
    const dot = document.getElementById('dot-server');
    const status = document.getElementById('status-server');

    if (!serverUrl) {
        dot.className = 'status-dot dot-yellow';
        status.textContent = '⚠️ 请填写服务端地址并点击保存';
        return;
    }

    dot.className = 'status-dot dot-yellow';
    status.textContent = '⏳ 正在连接服务端...';

    try {
        const resp = await fetch(serverUrl + '/api/config', {
            signal: AbortSignal.timeout(5000)
        });
        if (resp.ok) {
            const data = await resp.json();
            dot.className = 'status-dot dot-green';
            const parts = [];
            if (data.llm_model) parts.push(data.llm_model);
            if (data.cookies_configured) parts.push('Cookie ✅');
            else parts.push('Cookie ❌');
            status.textContent = `✅ 已连接 (${parts.join(', ')})`;
        } else {
            dot.className = 'status-dot dot-red';
            status.textContent = '❌ 服务端返回 ' + resp.status;
        }
    } catch (e) {
        console.error('checkServerStatus error:', e);
        const reason = e.name === 'TimeoutError' ? '超时' :
                       e.name === 'TypeError' ? '网络不通' : (e.message || '未知');
        dot.className = 'status-dot dot-red';
        status.textContent = '❌ 连接失败: ' + reason;
    }
}

// ── 一键采集 Cookie ──
async function collectCookie() {
    const btn = document.getElementById('btnCollect');
    btn.disabled = true;
    btn.textContent = '⏳ 采集中...';

    try {
        if (!serverUrl) {
            showMsg('error', '请先填写并保存服务端地址');
            return;
        }

        // 多域名合并
        const c1 = await chrome.cookies.getAll({ domain: '.xiaohongshu.com' });
        const c2 = await chrome.cookies.getAll({ domain: 'xiaohongshu.com' });
        const seen = new Set();
        const cookies = [];
        for (const c of [...c1, ...c2]) {
            if (!seen.has(c.name)) { seen.add(c.name); cookies.push(c); }
        }

        if (!cookies.length) {
            showMsg('error', '未找到 Cookie，请先打开 xiaohongshu.com 登录');
            return;
        }

        const cookieStr = cookies.map(c => `${c.name}=${c.value}`).join('; ');
        const hasA1 = cookies.some(c => c.name === 'a1');
        const hasWebSession = cookies.some(c => c.name === 'web_session');

        if (!hasA1) {
            showMsg('error', '缺少关键字段 a1，请确保已在小红书登录');
            return;
        }

        btn.textContent = '⏳ 发送中...';
        const resp = await fetch(serverUrl + '/api/cookie/collect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cookies: cookieStr, source: 'chrome_extension' })
        });

        const result = await resp.json();

        if (result.success) {
            let msg = '✅ ' + (result.message || 'Cookie 采集成功！');
            if (!hasWebSession) msg += '\n⚠️ 缺少 web_session，部分功能可能受限';
            showMsg('success', msg);
            checkServerStatus();
        } else {
            showMsg('error', '❌ ' + (result.message || '采集失败'));
        }
    } catch (e) {
        console.error('collectCookie error:', e);
        showMsg('error', '❌ 网络错误: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '🍪 一键采集 Cookie';
    }
}

// ── 手动刷新 ──
function manualRefresh() {
    checkXhsStatus();
    checkServerStatus();
    loadProxyState();
}

// ── 浏览器代理开关 ──
async function toggleProxy() {
    const toggle = document.getElementById('proxyToggle');
    const enabled = toggle.checked;
    try {
        chrome.runtime.sendMessage({ type: 'TOGGLE_PROXY', enabled });
        updateProxySlider(enabled);
        if (enabled) {
            showMsg('info', '🔄 浏览器代理已开启，正在监听小红书请求...');
        } else {
            showMsg('info', '⏸️ 浏览器代理已关闭');
        }
        setTimeout(loadProxyState, 500);
    } catch (e) {
        showMsg('error', '操作失败: ' + e.message);
        toggle.checked = !enabled;
    }
}

function updateProxySlider(enabled) {
    const slider = document.getElementById('proxySlider');
    const dot = document.getElementById('proxyDot');
    slider.style.background = enabled ? '#ff2442' : '#ccc';
    dot.style.transform = enabled ? 'translateX(18px)' : 'translateX(0)';
}

async function loadProxyState() {
    try {
        chrome.runtime.sendMessage({ type: 'GET_PROXY_STATS' }, (resp) => {
            if (!resp) return;
            const { stats, proxyEnabled } = resp;
            const toggle = document.getElementById('proxyToggle');
            toggle.checked = !!proxyEnabled;
            updateProxySlider(!!proxyEnabled);
            const statsEl = document.getElementById('proxyStats');
            if (proxyEnabled) {
                statsEl.textContent = `已转发 ${stats.totalForwarded || 0} 次 | 成功 ${stats.successCount || 0} | 失败 ${stats.failCount || 0}`;
            } else {
                statsEl.textContent = '';
            }
        });
    } catch (e) {}
}

// ── 消息显示 ──
function showMsg(type, text) {
    const el = document.getElementById('msg');
    el.className = `msg msg-${type}`;
    el.textContent = text;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 8000);
}
