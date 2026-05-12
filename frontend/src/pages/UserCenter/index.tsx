import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Card, Form, Input, Button, Select, Space, Typography, Tabs, message,
  QRCode, Spin, Alert, Tag, Divider, Row, Col, Statistic, Descriptions,
} from 'antd'
import {
  QrcodeOutlined, LockOutlined, ReloadOutlined, SaveOutlined,
  ThunderboltOutlined, UserOutlined, CheckCircleOutlined,
  CloseCircleOutlined, RobotOutlined, CloudOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import client from '../../api/client'
import { useAuthStore } from '../../stores/auth'

const { Title, Text, Paragraph } = Typography

export default function UserCenterPage() {
  const navigate = useNavigate()
  const setCookieConfigured = useAuthStore(s => s.setCookieConfigured)

  // ── Cookie / Login state ─────────────────────────────────────────────────
  const [cookieForm] = Form.useForm()
  const [cookieSaving, setCookieSaving] = useState(false)
  const [cookieTesting, setCookieTesting] = useState(false)
  const [cookieStatus, setCookieStatus] = useState<'unchecked' | 'valid' | 'invalid'>('unchecked')
  const [cookieUser, setCookieUser] = useState<string>('')

  // Browser QR login state
  const [browserSession, setBrowserSession] = useState<any>(null)
  const [browserStatus, setBrowserStatus] = useState<string>('')
  const [browserLoading, setBrowserLoading] = useState(false)
  const browserPollRef = useRef<any>(null)

  // QR Code login state
  const [qrSession, setQrSession] = useState<any>(null)
  const [qrStatus, setQrStatus] = useState('')
  const qrPollRef = useRef<any>(null)

  // ── 二次验证状态 ──────────────────────────────────────────────────────
  const [verifyType, setVerifyType] = useState<string>('')
  const [verifyData, setVerifyData] = useState<any>(null)
  const [verifyScreenshot, setVerifyScreenshot] = useState<string>('')
  const [verifyCode, setVerifyCode] = useState('')
  const [verifyLoading, setVerifyLoading] = useState(false)

  // ── AI Model state ─────────────────────────────────────────────────────
  const [aiForm] = Form.useForm()
  const [aiSaving, setAiSaving] = useState(false)
  const [aiTesting, setAiTesting] = useState(false)
  const [models, setModels] = useState<any[]>([])

  const stopBrowserPoll = useCallback(() => {
    if (browserPollRef.current) {
      clearInterval(browserPollRef.current)
      browserPollRef.current = null
    }
  }, [])

  const stopQrPoll = useCallback(() => {
    if (qrPollRef.current) {
      clearInterval(qrPollRef.current)
      qrPollRef.current = null
    }
  }, [])

  useEffect(() => () => { stopBrowserPoll(); stopQrPoll() }, [stopBrowserPoll, stopQrPoll])

  // ── Load existing config ──────────────────────────────────────────────
  const loadConfig = async () => {
    try {
      const r = await client.get('/config')
      const d = r.data
      cookieForm.setFieldsValue({ cookies: d.cookies })
      aiForm.setFieldsValue({
        llm_provider: d.llm_provider,
        llm_api_key: d.llm_api_key,
        llm_model: d.llm_model,
        llm_base_url: d.llm_base_url,
      })
      if (d.cookies_configured) {
        checkCookieStatus()
      }
    } catch (e: any) {
      message.error('加载配置失败')
    }
  }

  useEffect(() => { loadConfig() }, [])

  // ── Cookie operations ───────────────────────────────────────────────
  const onSaveCookie = async (values: any) => {
    setCookieSaving(true)
    try {
      await client.post('/config', values)
      message.success('Cookie已保存')
      checkCookieStatus()
    } catch (e: any) {
      message.error('保存失败: ' + (e.response?.data?.message || e.message))
    }
    setCookieSaving(false)
  }

  const checkCookieStatus = async () => {
    setCookieTesting(true)
    try {
      const r = await client.post('/config/test-cookie')
      if (r.data.success) {
        setCookieStatus('valid')
        const match = r.data.message.match(/用户:\s*(.+)/)
        setCookieUser(match ? match[1] : '已登录')
      } else {
        setCookieStatus('invalid')
        setCookieUser('')
      }
    } catch {
      setCookieStatus('unchecked')
    }
    setCookieTesting(false)
  }

  // ── Browser QR login ─────────────────────────────────────────────────
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
      }
    } catch {
      message.error('启动浏览器登录失败')
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
          setCookieConfigured(true)
          setBrowserSession(null)
          setBrowserStatus('')
          loadConfig()
        } else if (check.data.status === 'secondary_verify') {
          stopBrowserPoll()
          setVerifyType(check.data.verification_type)
          setVerifyData(check.data.verification_data)
          setVerifyScreenshot(check.data.verification_screenshot_b64)
        } else if (check.data.status === 'failed') {
          stopBrowserPoll()
          message.error(check.data.message)
          setBrowserSession(null)
          setBrowserStatus('')
          setVerifyType('')
        } else {
          setBrowserStatus(check.data.message || '等待扫码...')
        }
      } catch {}
    }, 3000)
  }, [stopBrowserPoll, setCookieConfigured])

  // ── QR Code login ────────────────────────────────────────────────────
  const startQrLogin = async () => {
    setBrowserLoading(true)
    stopBrowserPoll()
    stopQrPoll()
    try {
      const r = await client.post('/login/qrcode')
      if (r.data.success) {
        setQrSession(r.data)
        setQrStatus('请使用小红书APP扫描二维码')
        qrPollRef.current = setInterval(async () => {
          try {
            const check = await client.post('/login/check', { session_id: r.data.session_id })
            if (check.data.success && check.data.cookies) {
              clearInterval(qrPollRef.current)
              message.success(check.data.message || '登录成功！')
              setCookieConfigured(true)
              setQrSession(null)
              setQrStatus('')
              loadConfig()
            } else if (check.data.message?.includes('过期')) {
              clearInterval(qrPollRef.current)
              message.warning(check.data.message)
              setQrSession(null)
            } else {
              setQrStatus(check.data.message || '等待扫码...')
            }
          } catch {}
        }, 3000)
      } else {
        message.warning(r.data.message)
      }
    } catch {
      message.error('获取二维码失败')
    }
    setBrowserLoading(false)
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

  // ── AI Model operations ─────────────────────────────────────────────
  const onSaveAI = async (values: any) => {
    setAiSaving(true)
    try {
      await client.post('/config', values)
      message.success('AI配置已保存')
    } catch (e: any) {
      message.error('保存失败: ' + (e.response?.data?.message || e.message))
    }
    setAiSaving(false)
  }

  const onTestAI = async () => {
    setAiTesting(true)
    try {
      const values = aiForm.getFieldsValue()
      const r = await client.post('/config/test-ai', values)
      if (r.data.success) message.success(r.data.message)
      else message.warning(r.data.message)
    } catch (e: any) {
      message.error('AI测试失败: ' + (e.response?.data?.message || e.message))
    }
    setAiTesting(false)
  }

  const onLoadModels = async () => {
    try {
      const values = aiForm.getFieldsValue()
      const r = await client.post('/config/models', values)
      if (r.data.success) {
        setModels(r.data.models || [])
        message.success(`获取到 ${r.data.models?.length || 0} 个模型`)
      }
    } catch {}
  }

  // ── Render ──────────────────────────────────────────────────────────

  const cookieStatusTag = cookieStatus === 'valid'
    ? <Tag icon={<CheckCircleOutlined />} color="success">Cookie有效</Tag>
    : cookieStatus === 'invalid'
    ? <Tag icon={<CloseCircleOutlined />} color="error">Cookie无效</Tag>
    : <Tag color="default">未检测</Tag>

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <Title level={4} style={{ marginBottom: 24 }}>
        <UserOutlined style={{ marginRight: 8 }} />
        用户中心
      </Title>

      <Tabs
        defaultActiveKey="account"
        items={[
          {
            key: 'account',
            label: <span><LockOutlined /> 账号配置</span>,
            children: (
              <div>
                {/* Status Card */}
                <Card size="small" style={{ marginBottom: 16 }}>
                  <Row gutter={24}>
                    <Col span={8}>
                      <Statistic
                        title="小红书账号"
                        value={cookieUser || '未登录'}
                        prefix={cookieStatus === 'valid' ? <CheckCircleOutlined style={{ color: '#52c41a' }} /> : <CloseCircleOutlined style={{ color: '#ff4d4f' }} />}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title="Cookie状态"
                        value={cookieStatus === 'valid' ? '正常' : cookieStatus === 'invalid' ? '已失效' : '未检测'}
                        valueStyle={{ color: cookieStatus === 'valid' ? '#52c41a' : cookieStatus === 'invalid' ? '#ff4d4f' : '#999' }}
                      />
                    </Col>
                    <Col span={8}>
                      <Space direction="vertical">
                        <Button size="small" onClick={checkCookieStatus} loading={cookieTesting} icon={<ReloadOutlined />}>
                          刷新状态
                        </Button>
                      </Space>
                    </Col>
                  </Row>
                </Card>

                {/* Login Methods */}
                <Card title="扫码登录" size="small" style={{ marginBottom: 16 }}>
                  {!browserSession && !qrSession ? (
                    <div style={{ textAlign: 'center', padding: '16px 0' }}>
                      <Paragraph type="secondary" style={{ marginBottom: 16 }}>
                        推荐方式：打开小红书网页版或APP扫码登录，无需手动复制Cookie
                      </Paragraph>
                      <Space size="middle">
                        <Button type="primary" loading={browserLoading}
                          onClick={startBrowserLogin} icon={<QrcodeOutlined />}>
                          启动浏览器登录
                        </Button>
                        <Button loading={browserLoading}
                          onClick={startQrLogin} icon={<ReloadOutlined />}>
                          获取登录二维码
                        </Button>
                      </Space>
                    </div>
                  ) : browserSession ? (
                    <div style={{ textAlign: 'center', padding: '16px 0' }}>
                      {verifyType ? (
                        /* 二次验证UI */
                        <div>
                          <Alert
                            type="warning" showIcon
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
                          {(verifyType === 'phone_sms' || verifyType === 'captcha') && (
                            <Space direction="vertical" style={{ width: '100%' }} size="middle">
                              <Input
                                placeholder={verifyType === 'phone_sms' ? '请输入手机验证码' : '请输入图片验证码'}
                                value={verifyCode}
                                onChange={e => setVerifyCode(e.target.value)}
                                size="large" maxLength={6}
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
                          <Space style={{ marginTop: 16 }}>
                            <Button onClick={refreshVerification} icon={<ReloadOutlined />}>刷新截图</Button>
                            <Button type="link" danger onClick={cancelVerification}>取消</Button>
                          </Space>
                        </div>
                      ) : (
                        /* 等待扫码UI */
                        <div>
                          <Spin size="large" />
                          <Paragraph style={{ marginTop: 16 }}>{browserStatus}</Paragraph>
                          {browserSession.qr_image_b64 && (
                            <img src={`data:image/png;base64,${browserSession.qr_image_b64}`}
                              style={{ width: 200, height: 200, border: '1px solid #f0f0f0', borderRadius: 8, marginTop: 8 }}
                              alt="QR" />
                          )}
                          <div>
                            <Button type="link" onClick={() => { stopBrowserPoll(); setBrowserSession(null); setBrowserStatus(''); setVerifyType('') }}>
                              取消
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : qrSession ? (
                    <div style={{ textAlign: 'center', padding: '16px 0' }}>
                      <Paragraph>{qrStatus}</Paragraph>
                      {qrSession.qr_url ? (
                        <div style={{ marginBottom: 16 }}>
                          <QRCode value={qrSession.qr_url} size={180} />
                        </div>
                      ) : (
                        <Spin size="large" />
                      )}
                      <Button type="link" onClick={() => { stopQrPoll(); setQrSession(null); setQrStatus('') }}>
                        取消
                      </Button>
                    </div>
                  ) : null}
                </Card>

                {/* Manual Cookie Input */}
                <Card title="手动输入Cookie" size="small">
                  <Form form={cookieForm} onFinish={onSaveCookie} layout="vertical">
                    <Form.Item name="cookies" label={
                      <Space>
                        <span>小红书 Cookie</span>
                        {cookieStatusTag}
                      </Space>
                    }>
                      <Input.TextArea
                        rows={5}
                        placeholder="粘贴完整的Cookie字符串（如 a1=xxx; webId=xxx; web_session=xxx ...）"
                        style={{ fontFamily: 'monospace', fontSize: 12 }}
                      />
                    </Form.Item>
                    <Form.Item>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        从浏览器开发者工具 (F12 → Network → 找到 xiaohongshu.com 请求 → Headers → Cookie) 复制
                      </Text>
                    </Form.Item>
                    <Space>
                      <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={cookieSaving}>
                        保存Cookie
                      </Button>
                      <Button onClick={checkCookieStatus} loading={cookieTesting}>
                        测试有效性
                      </Button>
                    </Space>
                  </Form>
                </Card>
              </div>
            ),
          },
          {
            key: 'ai',
            label: <span><RobotOutlined /> 大模型配置</span>,
            children: (
              <Card>
                <Form form={aiForm} onFinish={onSaveAI} layout="vertical">
                  <Form.Item name="llm_provider" label="AI服务商" initialValue="deepseek">
                    <Select options={[
                      { value: 'deepseek', label: 'DeepSeek' },
                      { value: 'mimo', label: '小米MiMo' },
                      { value: 'openai', label: 'OpenAI兼容' },
                    ]} />
                  </Form.Item>
                  <Form.Item name="llm_api_key" label="API Key">
                    <Input.Password placeholder="sk-..." />
                  </Form.Item>
                  <Form.Item name="llm_model" label="模型名称">
                    <Select
                      showSearch
                      options={models.map(m => ({ value: m.id, label: m.name || m.id }))}
                      placeholder="先配置服务商和Key，再点「获取模型列表」"
                      notFoundContent="请先获取模型列表"
                    />
                  </Form.Item>
                  <Form.Item name="llm_base_url" label={
                    <Space>
                      <span>Base URL</span>
                      <Text type="secondary" style={{ fontSize: 12 }}>（可选，留空使用默认地址）</Text>
                    </Space>
                  }>
                    <Input placeholder="https://api.example.com/v1" />
                  </Form.Item>
                  <Space>
                    <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={aiSaving}>
                      保存配置
                    </Button>
                    <Button icon={<ThunderboltOutlined />} loading={aiTesting} onClick={onTestAI}>
                      测试连接
                    </Button>
                    <Button onClick={onLoadModels}>
                      获取模型列表
                    </Button>
                  </Space>
                </Form>
              </Card>
            ),
          },
        ]}
      />
    </div>
  )
}
