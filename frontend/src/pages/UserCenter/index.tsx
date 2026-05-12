import React, { useState, useEffect, useRef } from 'react'
import {
  Card, Input, Button, Typography, Tabs, message, Space, Tag, Descriptions,
  Row, Col, Statistic, Alert, Segmented, Spin, Image, InputRef
} from 'antd'
import {
  LockOutlined, SaveOutlined, CheckCircleOutlined, CloseCircleOutlined,
  InfoCircleOutlined, UserOutlined, QrcodeOutlined, BrowserOutlined,
  LoadingOutlined, CheckCircleFilled, ExclamationCircleFilled, GlobalOutlined
} from '@ant-design/icons'
import client from '../../api/client'
import { useAuthStore } from '../../stores/auth'

const { Title, Text, Paragraph } = Typography

// 登录方式类型
type LoginMethod = 'qrcode' | 'browser'

// 登录状态类型
interface LoginSession {
  sessionId: string
  method: LoginMethod
  status: 'waiting' | 'scanning' | 'confirmed' | 'completed' | 'failed' | 'secondary_verify'
  qrUrl?: string
  qrImageB64?: string
  message?: string
  cookies?: string
  verificationType?: string
  verificationData?: any
  verificationScreenshotB64?: string
  elapsed?: number
}

export default function UserCenterPage() {
  const { username, role } = useAuthStore()

  // Cookie管理状态
  const [cookieText, setCookieText] = useState('')
  const [cookieSaving, setCookieSaving] = useState(false)
  const [cookieTesting, setCookieTesting] = useState(false)
  const [cookieStatus, setCookieStatus] = useState<'unchecked' | 'valid' | 'invalid'>('unchecked')
  const [cookieUser, setCookieUser] = useState('')

  // 系统信息
  const [sysInfo, setSysInfo] = useState<any>(null)

  // 小红书登录状态
  const [loginMethod, setLoginMethod] = useState<LoginMethod>('qrcode')
  const [loginSession, setLoginSession] = useState<LoginSession | null>(null)
  const [loginLoading, setLoginLoading] = useState(false)
  const [pollTimer, setPollTimer] = useState<ReturnType<typeof setInterval> | null>(null)
  const [verifyCode, setVerifyCode] = useState('')
  const verifyInputRef = useRef<any>(null)

  // 清理轮询定时器
  useEffect(() => {
    return () => {
      if (pollTimer) {
        clearInterval(pollTimer)
      }
    }
  }, [pollTimer])

  // 加载初始数据
  useEffect(() => {
    // 加载当前配置
    client.get('/config').then(r => {
      const d = r.data
      setCookieText(d.cookies || '')
    }).catch(() => {})

    // 加载系统信息
    client.get('/health').then(r => setSysInfo(r.data)).catch(() => {})
  }, [])

  // ==================== Cookie管理相关函数 ====================

  const saveCookie = async () => {
    if (!cookieText.trim()) { message.warning('请输入Cookie'); return }
    setCookieSaving(true)
    try {
      await client.post('/config', { cookies: cookieText.trim() })
      message.success('Cookie 已保存')
    } catch (e: any) {
      message.error(e.response?.data?.detail || '保存失败')
    }
    setCookieSaving(false)
  }

  const testCookie = async () => {
    setCookieTesting(true)
    try {
      const r = await client.post('/config/test-cookie')
      if (r.data.success) {
        setCookieStatus('valid')
        setCookieUser(r.data.message)
        message.success(r.data.message)
      } else {
        setCookieStatus('invalid')
        setCookieUser(r.data.message)
        message.warning(r.data.message)
      }
    } catch (e: any) {
      setCookieStatus('invalid')
      message.error('测试失败: ' + (e.response?.data?.detail || e.message))
    }
    setCookieTesting(false)
  }

  // ==================== 小红书登录相关函数 ====================

  // 开始二维码登录
  const startQrcodeLogin = async () => {
    setLoginLoading(true)
    setLoginSession(null)
    try {
      const r = await client.post('/login/qrcode')
      if (r.data.success) {
        const session: LoginSession = {
          sessionId: r.data.session_id,
          method: 'qrcode',
          status: 'waiting',
          qrUrl: r.data.qr_url,
          message: '请使用小红书APP扫描二维码'
        }
        setLoginSession(session)
        message.info('二维码已生成，请扫码登录')
        startPolling(session.sessionId, 'qrcode')
      } else {
        message.error(r.data.message || '获取二维码失败')
      }
    } catch (e: any) {
      message.error(e.response?.data?.detail || '获取二维码失败')
    }
    setLoginLoading(false)
  }

  // 开始浏览器扫码登录
  const startBrowserLogin = async () => {
    setLoginLoading(true)
    setLoginSession(null)
    try {
      const r = await client.post('/login/browser/start')
      if (r.data.success) {
        const session: LoginSession = {
          sessionId: r.data.session_id,
          method: 'browser',
          status: r.data.status,
          qrImageB64: r.data.qr_image_b64,
          qrUrl: r.data.qr_url,
          message: '请使用小红书APP扫描二维码'
        }
        setLoginSession(session)
        message.info('浏览器登录已启动，请扫码登录')
        startPolling(session.sessionId, 'browser')
      } else {
        message.error(r.data.message || '启动浏览器登录失败')
      }
    } catch (e: any) {
      message.error(e.response?.data?.detail || '启动浏览器登录失败')
    }
    setLoginLoading(false)
  }

  // 开始轮询
  const startPolling = (sessionId: string, method: LoginMethod) => {
    if (pollTimer) {
      clearInterval(pollTimer)
    }

    const timer = setInterval(async () => {
      try {
        if (method === 'qrcode') {
          await pollQrcodeStatus(sessionId)
        } else {
          await pollBrowserStatus(sessionId)
        }
      } catch (e) {
        console.error('轮询错误:', e)
      }
    }, 3000)

    setPollTimer(timer)
  }

  // 轮询二维码登录状态
  const pollQrcodeStatus = async (sessionId: string) => {
    try {
      const r = await client.post('/login/check', { session_id: sessionId })

      if (r.data.success) {
        // 登录成功
        clearInterval(pollTimer!)
        setPollTimer(null)

        const newSession: LoginSession = {
          ...loginSession!,
          status: 'completed',
          message: r.data.message,
          cookies: r.data.cookies
        }
        setLoginSession(newSession)

        // 保存Cookie
        await saveCookies(r.data.cookies, r.data.message)
      } else if (r.data.message?.includes('确认')) {
        setLoginSession(prev => prev ? { ...prev, status: 'confirmed', message: r.data.message } : null)
      } else {
        setLoginSession(prev => prev ? { ...prev, message: r.data.message } : null)
      }
    } catch (e: any) {
      console.error('检查二维码状态失败:', e)
    }
  }

  // 轮询浏览器登录状态
  const pollBrowserStatus = async (sessionId: string) => {
    try {
      const r = await client.post('/login/browser/check', { session_id: sessionId })

      if (r.data.success) {
        // 登录成功
        clearInterval(pollTimer!)
        setPollTimer(null)

        const newSession: LoginSession = {
          ...loginSession!,
          status: 'completed',
          message: r.data.message,
          cookies: r.data.cookies
        }
        setLoginSession(newSession)

        // 保存Cookie
        await saveCookies(r.data.cookies, r.data.message)
      } else if (r.data.status === 'secondary_verify') {
        // 需要二次验证
        setLoginSession(prev => prev ? {
          ...prev,
          status: 'secondary_verify',
          message: r.data.message,
          verificationType: r.data.verification_type,
          verificationData: r.data.verification_data,
          verificationScreenshotB64: r.data.verification_screenshot_b64
        } : null)
      } else if (r.data.status === 'failed') {
        clearInterval(pollTimer!)
        setPollTimer(null)
        setLoginSession(prev => prev ? { ...prev, status: 'failed', message: r.data.message } : null)
        message.error(r.data.message || '登录失败')
      } else {
        // 更新二维码图片（可能会刷新）
        setLoginSession(prev => prev ? {
          ...prev,
          status: r.data.status || 'waiting',
          message: r.data.message,
          qrImageB64: r.data.qr_image_b64 || prev.qrImageB64,
          qrUrl: r.data.qr_url || prev.qrUrl,
          elapsed: r.data.elapsed
        } : null)
      }
    } catch (e: any) {
      console.error('检查浏览器登录状态失败:', e)
    }
  }

  // 提交二次验证
  const submitVerification = async () => {
    if (!verifyCode.trim()) {
      message.warning('请输入验证码')
      return
    }

    setLoginLoading(true)
    try {
      const r = await client.post('/login/browser/verify', {
        session_id: loginSession!.sessionId,
        type: loginSession!.verificationType || 'phone_sms',
        code: verifyCode.trim()
      })

      if (r.data.success) {
        message.success('验证已提交，正在处理...')
        setVerifyCode('')
        // 继续轮询
        setLoginSession(prev => prev ? { ...prev, status: 'waiting', verificationType: undefined } : null)
      } else {
        message.error(r.data.message || '验证失败')
      }
    } catch (e: any) {
      message.error(e.response?.data?.detail || '验证失败')
    }
    setLoginLoading(false)
  }

  // 刷新二维码（二次验证）
  const refreshVerification = async () => {
    setLoginLoading(true)
    try {
      const r = await client.post('/login/browser/verify', {
        session_id: loginSession!.sessionId,
        type: 'refresh',
        code: ''
      })

      if (r.data.success) {
        message.info('已刷新，请重新扫描')
        setLoginSession(prev => prev ? { ...prev, status: 'waiting', verificationType: undefined } : null)
      }
    } catch (e: any) {
      message.error('刷新失败')
    }
    setLoginLoading(false)
  }

  // 保存Cookie到后端
  const saveCookies = async (cookies: string, successMsg: string) => {
    try {
      await client.post('/config', { cookies })
      message.success(successMsg || '登录成功！Cookie已保存')
    } catch (e: any) {
      message.error('Cookie保存失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  // 停止登录
  const stopLogin = async () => {
    if (pollTimer) {
      clearInterval(pollTimer)
      setPollTimer(null)
    }

    if (loginSession && loginSession.method === 'browser') {
      try {
        await client.post('/login/browser/stop', { session_id: loginSession.sessionId })
      } catch (e) {
        // ignore
      }
    }

    setLoginSession(null)
    setVerifyCode('')
    message.info('已停止登录')
  }

  // 渲染登录方式选择
  const renderLoginMethodSelector = () => (
    <Segmented
      options={[
        {
          label: <span><QrcodeOutlined /> 二维码登录</span>,
          value: 'qrcode'
        },
        {
          label: <span><GlobalOutlined /> 浏览器扫码登录</span>,
          value: 'browser'
        }
      ]}
      value={loginMethod}
      onChange={(value) => {
        if (loginSession && (loginSession.status === 'waiting' || loginSession.status === 'scanning')) {
          stopLogin()
        }
        setLoginMethod(value as LoginMethod)
      }}
      style={{ marginBottom: 16 }}
    />
  )

  // 渲染二维码登录界面
  const renderQrcodeLogin = () => {
    if (!loginSession || loginSession.method !== 'qrcode') {
      return (
        <Card>
          <Space direction="vertical" size="large" style={{ width: '100%', textAlign: 'center' }}>
            <Alert
              type="info"
              showIcon
              message="二维码登录"
              description="使用小红书APP扫描二维码，快速登录"
            />
            <Button
              type="primary"
              size="large"
              icon={<QrcodeOutlined />}
              loading={loginLoading}
              onClick={startQrcodeLogin}
            >
              获取二维码
            </Button>
          </Space>
        </Card>
      )
    }

    return renderLoginProgress()
  }

  // 渲染浏览器登录界面
  const renderBrowserLogin = () => {
    if (!loginSession || loginSession.method !== 'browser') {
      return (
        <Card>
          <Space direction="vertical" size="large" style={{ width: '100%', textAlign: 'center' }}>
            <Alert
              type="warning"
              showIcon
              message="浏览器扫码登录"
              description="使用Playwright启动真实浏览器，模拟扫码登录，可能需要处理二次验证"
            />
            <Button
              type="primary"
              size="large"
              icon={<BrowserOutlined />}
              loading={loginLoading}
              onClick={startBrowserLogin}
            >
              启动浏览器登录
            </Button>
          </Space>
        </Card>
      )
    }

    return renderLoginProgress()
  }

  // 渲染登录进度
  const renderLoginProgress = () => {
    if (!loginSession) return null

    const { status, message: msg, qrUrl, qrImageB64, verificationType, verificationData, verificationScreenshotB64 } = loginSession

    return (
      <Card>
        <Space direction="vertical" size="large" style={{ width: '100%', textAlign: 'center' }}>
          {/* 状态提示 */}
          <Alert
            type={
              status === 'completed' ? 'success' :
                status === 'failed' ? 'error' :
                  status === 'secondary_verify' ? 'warning' : 'info'
            }
            showIcon
            message={
              status === 'completed' ? '登录成功' :
                status === 'failed' ? '登录失败' :
                  status === 'secondary_verify' ? '需要验证' :
                    status === 'confirmed' ? '已确认，正在登录...' : '等待扫码'
            }
            description={msg}
          />

          {/* 二维码显示 */}
          {(status === 'waiting' || status === 'scanning' || status === 'confirmed') && (
            <div>
              {loginMethod === 'qrcode' && qrUrl ? (
                <Image
                  src={qrUrl}
                  alt="小红书登录二维码"
                  style={{ maxWidth: 200, maxHeight: 200 }}
                  fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMIAAABCAYAAAB/EC+vAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAALEgAACxIB0t1+/AAAABZ0RVh0Q3JlYXRpb24gVGltZQAxMC8yOS8xMS42Vlx1AAAAAElFTkSuQmCC"
                />
              ) : loginMethod === 'browser' && qrImageB64 ? (
                <Image
                  src={`data:image/png;base64,${qrImageB64}`}
                  alt="小红书登录二维码"
                  style={{ maxWidth: 200, maxHeight: 200 }}
                />
              ) : (
                <Spin indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
              )}
            </div>
          )}

          {/* 二次验证界面 */}
          {status === 'secondary_verify' && (
            <Card size="small" style={{ textAlign: 'left' }}>
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Alert
                  type="warning"
                  message="需要二次验证"
                  description={verificationData?.message || '请完成验证'}
                />

                {/* 显示验证截图 */}
                {verificationScreenshotB64 && (
                  <div style={{ textAlign: 'center' }}>
                    <Image
                      src={`data:image/png;base64,${verificationScreenshotB64}`}
                      alt="验证截图"
                      style={{ maxWidth: '100%' }}
                    />
                  </div>
                )}

                {/* 验证码输入 */}
                {verificationType === 'phone_sms' && (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Text>请输入手机验证码：</Text>
                    <Space>
                      <Input
                        placeholder="请输入验证码"
                        value={verifyCode}
                        onChange={e => setVerifyCode(e.target.value)}
                        onPressEnter={submitVerification}
                        style={{ width: 200 }}
                      />
                      <Button
                        type="primary"
                        onClick={submitVerification}
                        loading={loginLoading}
                      >
                        提交
                      </Button>
                    </Space>
                  </Space>
                )}

                {/* 刷新按钮（其他验证类型） */}
                {verificationType !== 'phone_sms' && (
                  <Button onClick={refreshVerification} loading={loginLoading}>
                    刷新二维码
                  </Button>
                )}
              </Space>
            </Card>
          )}

          {/* 操作按钮 */}
          <Space>
            {status !== 'completed' && status !== 'failed' && (
              <Button onClick={stopLogin}>停止登录</Button>
            )}
            {(status === 'completed' || status === 'failed') && (
              <Button onClick={() => {
                setLoginSession(null)
                setVerifyCode('')
              }}>
                重新登录
              </Button>
            )}
          </Space>
        </Space>
      </Card>
    )
  }

  // ==================== 主渲染 ====================

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto' }}>
      <Title level={3}>👤 个人中心</Title>

      <Tabs items={[
        {
          key: 'cookie',
          label: <span><LockOutlined /> Cookie 管理</span>,
          children: (
            <Card>
              <Alert
                type="info"
                showIcon
                message="小红书 Cookie 用于内容采集和发布"
                description={
                  <div>
                    <Paragraph style={{ margin: '4px 0 0' }}>
                      从浏览器开发者工具（F12 → Network → 找到 xiaohongshu.com 请求 → Headers → Cookie）复制完整的 Cookie 字符串。
                    </Paragraph>
                    <Paragraph style={{ margin: '4px 0 0' }}>
                      <Text strong>关键字段：</Text> web_session, a1, gid, webId
                    </Paragraph>
                  </div>
                }
                style={{ marginBottom: 16 }}
              />

              <Input.TextArea
                rows={6}
                value={cookieText}
                onChange={e => setCookieText(e.target.value)}
                placeholder="粘贴完整的Cookie字符串（如 a1=xxx; webId=xxx; web_session=xxx ...）"
                style={{ fontFamily: 'monospace', fontSize: 12, marginBottom: 12 }}
              />

              <Space>
                <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  loading={cookieSaving}
                  onClick={saveCookie}
                >
                  保存 Cookie
                </Button>
                <Button
                  icon={<CheckCircleOutlined />}
                  loading={cookieTesting}
                  onClick={testCookie}
                >
                  验证 Cookie
                </Button>
                {cookieStatus === 'valid' && <Tag color="green">{cookieUser}</Tag>}
                {cookieStatus === 'invalid' && <Tag color="red">{cookieUser}</Tag>}
              </Space>
            </Card>
          ),
        },
        {
          key: 'xhs-login',
          label: <span><QrcodeOutlined /> 小红书登录</span>,
          children: (
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              {renderLoginMethodSelector()}

              {loginMethod === 'qrcode' ? renderQrcodeLogin() : renderBrowserLogin()}
            </Space>
          ),
        },
        {
          key: 'info',
          label: <span><InfoCircleOutlined /> 关于</span>,
          children: (
            <Card>
              <Descriptions column={1} bordered>
                <Descriptions.Item label="平台名称">🥔 土豆小红书助手</Descriptions.Item>
                <Descriptions.Item label="当前版本">v2.2.0</Descriptions.Item>
                <Descriptions.Item label="当前用户">
                  <Space>
                    <Tag icon={<UserOutlined />} color="blue">{username}</Tag>
                    {role === 'admin' ? <Tag color="red">管理员</Tag> : <Tag>用户</Tag>}
                  </Space>
                </Descriptions.Item>
                <Descriptions.Item label="技术栈">FastAPI + React 19 + SQLite + Playwright</Descriptions.Item>
                <Descriptions.Item label="访问地址">
                  <a href="https://xhs.maomaoxia.top" target="_blank" rel="noopener">xhs.maomaoxia.top</a>
                </Descriptions.Item>
              </Descriptions>
            </Card>
          ),
        },
      ]} />
    </div>
  )
}
