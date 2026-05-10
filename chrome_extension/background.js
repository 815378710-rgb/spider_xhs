// 小红书浏览器代理 - background.js (v2.0)
// 监听来自服务端的API请求，用真实浏览器发起，返回响应
// 这样绕过服务器端的反爬检测

let serverUrl = '';
let proxyEnabled = false;
let pendingRequests = new Map(); // requestId -> {resolve, reject, timer}
let stats = {
    totalForwarded: 0,
    successCount: 0,
    failCount: 0,
    lastForwardTime: null,
};

// ── 初始化 ──
chrome.runtime.onInstalled.addListener(() => {
    chrome.storage.local.get(['serverUrl', 'proxyEnabled'], (data) => {
        serverUrl = data.serverUrl || 'http://192.168.68.162:5000';
        proxyEnabled = data.proxyEnabled || false;
        console.log('[Proxy] 初始化:', { serverUrl, proxyEnabled });
        if (proxyEnabled) startPolling();
    });
});

// ── 监听来自 popup 的消息 ──
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === 'SET_SERVER_URL') {
        serverUrl = msg.url;
        chrome.storage.local.set({ serverUrl: msg.url });
        sendResponse({ ok: true });
    } else if (msg.type === 'TOGGLE_PROXY') {
        proxyEnabled = msg.enabled;
        chrome.storage.local.set({ proxyEnabled: msg.enabled });
        if (msg.enabled) startPolling();
        else stopPolling();
        sendResponse({ ok: true });
    } else if (msg.type === 'GET_PROXY_STATS') {
        sendResponse({ stats, serverUrl, proxyEnabled });
    } else if (msg.type === 'FORWARD_NOW') {
        // 立即执行一次轮询
        pollAndForward().then(r => sendResponse(r));
        return true; // async
    }
    return false;
});

// ── 轮询机制 ──
let pollTimer = null;
const POLL_INTERVAL = 3000; // 3秒轮询

function startPolling() {
    if (pollTimer) return;
    console.log('[Proxy] 开始轮询，间隔', POLL_INTERVAL, 'ms');
    pollTimer = setInterval(() => pollAndForward(), POLL_INTERVAL);
    // 立即执行一次
    pollAndForward();
}

function stopPolling() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
    console.log('[Proxy] 停止轮询');
}

// ── 核心：轮询 + 转发 ──
async function pollAndForward() {
    if (!proxyEnabled || !serverUrl) return;

    try {
        // 从服务端拉取待转发的请求
        const resp = await fetch(serverUrl + '/api/proxy/pending', {
            method: 'GET',
            signal: AbortSignal.timeout(5000),
        });
        if (!resp.ok) return;

        const data = await resp.json();
        if (!data.success || !data.requests || data.requests.length === 0) return;

        console.log(`[Proxy] 收到 ${data.requests.length} 个待转发请求`);

        // 逐个转发
        for (const req of data.requests) {
            await forwardRequest(req);
        }
    } catch (e) {
        // 静默处理轮询错误
        console.debug('[Proxy] 轮询失败:', e.message);
    }
}

// ── 转发单个请求 ──
async function forwardRequest(req) {
    const { request_id, method, url, headers, body } = req;

    try {
        // 用真实浏览器环境发起请求
        const fetchOptions = {
            method: method || 'GET',
            headers: headers || {},
            credentials: 'include', // 携带浏览器 cookie
        };

        if (body && method !== 'GET') {
            fetchOptions.body = typeof body === 'string' ? body : JSON.stringify(body);
        }

        const resp = await fetch(url, fetchOptions);
        const respText = await resp.text();
        let respData;
        try {
            respData = JSON.parse(respText);
        } catch {
            respData = { raw: respText };
        }

        stats.totalForwarded++;
        stats.successCount++;
        stats.lastForwardTime = new Date().toISOString();

        // 将结果发回服务端
        await fetch(serverUrl + '/api/proxy/result', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                request_id,
                success: true,
                status: resp.status,
                data: respData,
            }),
        });

        console.log(`[Proxy] ✅ ${request_id} -> ${resp.status}`);
    } catch (e) {
        stats.totalForwarded++;
        stats.failCount++;
        stats.lastForwardTime = new Date().toISOString();

        // 报告失败
        try {
            await fetch(serverUrl + '/api/proxy/result', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    request_id,
                    success: false,
                    error: e.message,
                }),
            });
        } catch {}

        console.log(`[Proxy] ❌ ${request_id}: ${e.message}`);
    }
}
