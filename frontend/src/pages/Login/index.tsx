import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Card, Tabs, Input, Button, Typography, Space, Steps, Result, Spin, message, QRCode, Tag, Alert } from 'antd'
import { QrcodeOutlined, MobileOutlined, LockOutlined, ReloadOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import client from '../../api/client'
import { useAuthStore } from '../../stores/auth'

const { Title, Text, Paragraph } = Typography

export default function LoginPage() {
const navigate = useNavigate()
  const setCookieConfigured = useAuthStore(s => s.setCookieConfigured)

  // Browser QR login state
  const [browserSession, setBrowserSession] = useState<any>(null)
  const [browserStatus, setBrowserStatus] = useState<string>('')
  const [browserLoading, setBrowserLoading] = useState(false)
  const browserPollRef = useRef<any>(null)

  // ── 二次验证状态 ────────────────────────────────────────────────────
  const [verifyType, setVerifyType] = useState<string>('')
  const [verifyData, setVerifyData] = useState<any>(null)
  const [verifyScreenshot, setVerifyScreenshot] = useState<string>('')
  const [verifyCode, setVerifyCode] = useState('')
  const [verifyLoading, setVerifyLoading] = useState(false)

  // Phone login state
  const [phone, setPhone] = useState('')
  const [phoneSession, setPhoneSession] = useState('')
  const [phoneCode, setPhoneCode] = useState('')
  const [phoneStep, setPhoneStep] = useState(0) // 0: enter phone, 1: enter code
  const [phoneLoading, setPhoneLoading] = useState(false)

  // Cookie input
  const [cookieText, setCookieText] = useState('')
  const [cookieSaving, setCookieSaving] = useState(false)

  const stopBrowserPoll = useCallback(() => {
    if (browserPollRef.current) {
      clearInterval(browserPollRef.current)
      browserPollRef.current = null
    }
  }, [])

  useEffect(() => () => stopBrowserPoll(), [stopBrowserPoll])

  // ── Browser QR login ─────────────────────────────────────────────────────
  const startBrowserLogin = async () => {
    setBrowserLoading(true)
    stopBrowserPoll()
    try {
      const r = await client.post('/login/browser/start')
      if (r.data.success) {
        setBrowserSession(r.data)
        setBrowserStatus('请在弹出的浏览器窗口中扫码登录...')
        startBrowserPoll(r.data.session_id)
      } else {
        message.warning(r.data.message)
        setBrowserSession(null)
      }
    } catch {
      message.error('启动浏览器登录失败，请尝试其他方式')
    }
    setBrowserLoading(false)
  }

  const startBrowserPoll = useCallback((sid: string) => {
    stopBrowserPoll()
    browserPollRef.current = setInterval(async () => {
      try {
        const check = await client.post('/login/browser/check', { session_id: sid })
        if (check.data.success && check.data.cookies) {
          stopBrowserPoll()
          setVerifyType('')
          message.success(check.data.message || '登录成功！')
          localStorage.setItem('xhs_cookie_configured', '1')
          navigate('/')
        } else if (check.data.status === 'secondary_verify') {
          stopBrowserPoll()
          setVerifyType(check.data.verification_type)
          setVerifyData(check.data.verification_data)
          setVerifyScreenshot(check.data.verification_screenshot_b64)
          message.warning(check.data.verification_data?.message || '需要完成二次验证')
        } else if (check.data.status === 'failed') {
          stopBrowserPoll()
          message.error(check.data.message)
          setBrowserStatus('')
          setBrowserSession(null)
          setVerifyType('')
        } else {
          setBrowserStatus(check.data.message || '等待扫码...')
        }
      } catch {}
    }, 3000)
  }, [stopBrowserPoll, navigate])

  // ── QR Code login (API-based) ────────────────────────────────────────────
  const [qrSession, setQrSession] = useState<any>(null)
  const [qrStatus, setQrStatus] = useState('')
  const qrPollRef = useRef<any>(null)

  const startQrLogin = async () => {
    setBrowserLoading(true)
    stopBrowserPoll()
    try {
      const r = await client.post('/login/qrcode')
      if (r.data.success) {
        setQrSession(r.data)
        setQrStatus('请使用小红书APP扫描二维码')
        // Poll status
        qrPollRef.current = setInterval(async () => {
          try {
            const check = await client.post('/login/check', { session_id: r.data.session_id })
            if (check.data.success && check.data.cookies) {
              clearInterval(qrPollRef.current)
              message.success(check.data.message || '登录成功！')
              localStorage.setItem('xhs_cookie_configured', '1')
              navigate('/')
            } else if (check.data.message?.includes('过期')) {
              clearInterval(qrPollRef.current)
              message.warning(check.data.message)
              setQrSession(null)
            } else {
              setQrStatus(check.data.message || '等待扫码...')
            }
          } catch {
            // Keep polling
          }
        }, 3000)
      } else {
        message.warning(r.data.message)
      }
    } catch {
      message.error('获取二维码失败')
    }
    setBrowserLoading(false)
  }

  useEffect(() => () => { if (qrPollRef.current) clearInterval(qrPollRef.current) }, [])

  // ── Phone login ──────────────────────────────────────────────────────────
  const sendPhoneCode = async () => {
    if (!phone.trim()) { message.warning('请输入手机号'); return }
    setPhoneLoading(true)
    try {
      const r = await client.post('/login/phone/send', { phone: phone.trim() })
      if (r.data.success) {
        message.success(r.data.message)
        setPhoneSession(r.data.session_id)
        setPhoneStep(1)
      } else {
        message.error(r.data.message)
      }
    } catch (e: any) {
      message.error(e.response?.data?.message || '发送验证码失败')
    }
    setPhoneLoading(false)
  }

  const verifyPhoneCode = async () => {
    if (!phoneCode.trim()) { message.warning('请输入验证码'); return }
    setPhoneLoading(true)
    try {
      const r = await client.post('/login/phone/verify', { session_id: phoneSession, code: phoneCode.trim() })
      if (r.data.success) {
        message.success(r.data.message || '登录成功！')
        localStorage.setItem('xhs_cookie_configured', '1')
        navigate('/')
      } else {
        message.error(r.data.message)
      }
    } catch (e: any) {
      message.error(e.response?.data?.message || '验证失败')
    }
    setPhoneLoading(false)
  }

  // ── Cookie manual input ──────────────────────────────────────────────────
  const saveCookie = async () => {
    if (!cookieText.trim()) { message.warning('请输入Cookie'); return }
    setCookieSaving(true)
    try {
      await client.post('/config', { cookies: cookieText.trim() })
      // Test it
      const test = await client.post('/config/test-cookie')
      if (test.data.success) {
        message.success(test.data.message)
        localStorage.setItem('xhs_cookie_configured', '1')
        navigate('/')
      } else {
        message.warning('Cookie已保存，但测试未通过：' + test.data.message)
        localStorage.setItem('xhs_cookie_configured', '1')
        navigate('/')
      }
    } catch (e: any) {
      message.error(e.response?.data?.message || '保存失败')
    }
    setCookieSaving(false)
  }

  // ── Skip login ───────────────────────────────────────────────────────────
  const skipLogin = () => {
    setCookieConfigured(true)
    navigate('/')
  }

  // ── 二次验证操作 ──────────────────────────────────────────────────────
  const submitVerification = async () => {
    if (!verifyCode.trim() && verifyType !== 'device_qr') {
      message.warning('请输入验证码')
      return
    }
    setVerifyLoading(true)
    try {
      const r = await client.post('/login/browser/verify', {
        session_id: browserSession.session_id,
        type: verifyType,
        code: verifyCode.trim(),
      })
      if (r.data.success) {
        message.success('验证已提交，正在处理...')
        setVerifyCode('')
        // 重新开始轮询
        startBrowserPoll(browserSession.session_id)
      } else {
        message.error(r.data.message)
      }
    } catch {
      message.error('提交验证失败')
    }
    setVerifyLoading(false)
  }

  const confirmDeviceScan = async () => {
    setVerifyLoading(true)
    try {
      await client.post('/login/browser/verify', {
        session_id: browserSession.session_id,
        type: 'device_qr',
      })
      message.info('已确认，等待页面跳转...')
      startBrowserPoll(browserSession.session_id)
    } catch {
      message.error('确认失败')
    }
    setVerifyLoading(false)
  }

  const refreshVerification = async () => {
    try {
      await client.post('/login/browser/verify', {
        session_id: browserSession.session_id,
        type: 'refresh',
      })
      // 重新check获取最新截图
      const check = await client.post('/login/browser/check', { session_id: browserSession.session_id })
      if (check.data.verification_screenshot_b64) {
        setVerifyScreenshot(check.data.verification_screenshot_b64)
      }
      message.success('已刷新')
    } catch {
      message.error('刷新失败')
    }
  }

  const cancelVerification = () => {
    setVerifyType('')
    setVerifyData(null)
    setVerifyScreenshot('')
    setVerifyCode('')
    setBrowserSession(null)
    setBrowserStatus('')
    stopBrowserPoll()
  }

  const tabItems = [
    {
      key: 'browser',
      label: <span><QrcodeOutlined /> 浏览器扫码登录</span>,
      children: (
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          {!browserSession && !qrSession ? (
            <>
              <Paragraph type="secondary">推荐方式：打开小红书网页版，使用APP扫码登录</Paragraph>
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Button type="primary" size="large" loading={browserLoading}
                  onClick={startBrowserLogin} icon={<QrcodeOutlined />}
                  style={{ width: 280, height: 48 }}>
                  启动浏览器登录
                </Button>
                <Text type="secondary">或者使用 API 二维码方式：</Text>
                <Button size="large" loading={browserLoading}
                  onClick={startQrLogin} icon={<ReloadOutlined />}
                  style={{ width: 280 }}>
                  获取登录二维码
                </Button>
              </Space>
            </>
          ) : browserSession ? (
            <div>
              {verifyType ? (
                /* ── 二次验证桥接UI ── */
                <div style={{ padding: '20px 0', textAlign: 'center' }}>
                  <Alert
                    type="warning"
                    showIcon
                    message={verifyData?.message || '需要完成验证'}
                    description={verifyData?.hint || '请完成页面上的验证'}
                    style={{ marginBottom: 16, textAlign: 'left' }}
                  />
                  {verifyScreenshot && (
                    <div style={{ marginBottom: 16 }}>
                      <img
                        src={`data:image/png;base64,${verifyScreenshot}`}
                        style={{ maxWidth: '100%', maxHeight: 300, border: '1px solid #f0f0f0', borderRadius: 8 }}
                        alt="验证截图"
                      />
                    </div>
                  )}
                  {verifyType === 'phone_sms' && (
                    <Space direction="vertical" style={{ width: '100%' }} size="middle">
                      <Input
                        placeholder="请输入手机验证码"
                        value={verifyCode}
                        onChange={e => setVerifyCode(e.target.value)}
                        size="large"
                        maxLength={6}
                      />
                      <Button type="primary" block size="large" loading={verifyLoading}
                        onClick={submitVerification}>
                        提交验证码
                      </Button>
                    </Space>
                  )}
                  {verifyType === 'captcha' && (
                    <Space direction="vertical" style={{ width: '100%' }} size="middle">
                      <Input
                        placeholder="请输入图片中的验证码"
                        value={verifyCode}
                        onChange={e => setVerifyCode(e.target.value)}
                        size="large"
                      />
                      <Button type="primary" block size="large" loading={verifyLoading}
                        onClick={submitVerification}>
                        提交验证码
                      </Button>
                    </Space>
                  )}
                  {verifyType === 'device_qr' && (
                    <Space direction="vertical" style={{ width: '100%' }} size="middle">
                      <Paragraph type="secondary">
                        请打开小红书APP，使用「扫一扫」扫描上方截图中的二维码
                      </Paragraph>
                      <Button type="primary" block size="large" loading={verifyLoading}
                        onClick={confirmDeviceScan}>
                        我已完成扫码
                      </Button>
                    </Space>
                  )}
                  {verifyType === 'unknown' && (
                    <Space direction="vertical" style={{ width: '100%' }} size="middle">
                      <Paragraph type="secondary">
                        请查看截图中的页面内容，完成相应操作后点击下方按钮
                      </Paragraph>
                      <Button type="primary" block size="large" loading={verifyLoading}
                        onClick={submitVerification}>
                        我已完成验证
                      </Button>
                    </Space>
                  )}
                  <Space style={{ marginTop: 16 }}>
                    <Button onClick={refreshVerification} icon={<ReloadOutlined />}>
                      刷新截图
                    </Button>
                    <Button type="link" danger onClick={cancelVerification}>
                      取消验证，返回
                    </Button>
                  </Space>
                </div>
              ) : (
                /* ── 正常扫码等待UI ── */
                <div>
                  <Spin size="large" />
                  <Paragraph style={{ marginTop: 16 }}>{browserStatus}</Paragraph>
                  {browserSession.qr_image_b64 && (
                    <img src={`data:image/png;base64,${browserSession.qr_image_b64}`}
                      style={{ width: 200, height: 200, border: '1px solid #f0f0f0', borderRadius: 8 }} alt="QR" />
                  )}
                  <Button type="link" onClick={() => { stopBrowserPoll(); setBrowserSession(null); setBrowserStatus(''); setVerifyType('') }}>
                    取消并返回
                  </Button>
                </div>
              )}
            </div>
          ) : qrSession ? (
            <div>
              <Paragraph>{qrStatus}</Paragraph>
              {qrSession.qr_url ? (
                <div style={{ marginBottom: 16 }}>
                  <QRCode value={qrSession.qr_url} size={200} />
                </div>
              ) : (
                <Spin size="large" />
              )}
              <Button type="link" onClick={() => { if (qrPollRef.current) clearInterval(qrPollRef.current); setQrSession(null); setQrStatus('') }}>
                取消并返回
              </Button>
            </div>
          ) : null}
        </div>
      ),
    },
    {
      key: 'phone',
      label: <span><MobileOutlined /> 手机号登录 (暂不支持)</span>,
      disabled: true,
      children: (
        <div style={{ padding: '20px 0', textAlign: 'center' }}>
          <Alert
            type="warning"
            showIcon
            message="手机号登录暂不可用"
            description="由于小红书 API 变更，手机号登录目前无法获取有效会话。请使用浏览器扫码登录或手动输入 Cookie。"
            style={{ textAlign: 'left' }}
          />
        </div>
      ),
    },
    {
      key: 'cookie',
      label: <span><LockOutlined /> 手动输入Cookie</span>,
      children: (
        <div style={{ padding: '20px 0' }}>
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Paragraph type="secondary">
              从浏览器开发者工具 (F12 → Network → 找到 xiaohongshu.com 请求 → Headers → Cookie) 复制完整的 Cookie 字符串
            </Paragraph>
            <Input.TextArea rows={8} value={cookieText}
              onChange={e => setCookieText(e.target.value)}
              placeholder="粘贴完整的Cookie字符串（如 a1=xxx; webId=xxx; web_session=xxx ...）"
              style={{ fontFamily: 'monospace', fontSize: 12 }} />
            <Button type="primary" block size="large" loading={cookieSaving}
              onClick={saveCookie} icon={<LockOutlined />}>
              保存并登录
            </Button>
          </Space>
        </div>
      ),
    },
  ]

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg, #fff5f5 0%, #fff 50%, #f6ffed 100%)' }}>
      <Card style={{ width: 480, boxShadow: '0 8px 24px rgba(0,0,0,0.08)' }}
        title={
          <div style={{ textAlign: 'center' }}>
            <Title level={3} style={{ margin: 0 }}>🥔 土豆小红书助手</Title>
            <Text type="secondary">登录后开始使用</Text>
          </div>
        }
      >
        <Tabs items={tabItems} centered />
        <div style={{ textAlign: 'center', marginTop: 8 }}>
          <Button type="link" onClick={skipLogin}>跳过登录，直接使用</Button>
        </div>
      </Card>
    </div>
  )
}
