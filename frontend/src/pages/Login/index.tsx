import React, { useState } from 'react'
import { Card, Tabs, Input, Button, Typography, Space, Form, Alert, App } from 'antd'
import { UserOutlined, LockOutlined, KeyOutlined, QrcodeOutlined, MobileOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import client from '../../api/client'
import { useAuthStore } from '../../stores/auth'

const { Title, Text, Paragraph } = Typography

export default function LoginPage() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const login = useAuthStore(s => s.login)
  
  // 注册表单
  const [registerForm, setRegisterForm] = useState({ username: '', password: '', confirmPassword: '', licenseKey: '' })
  const [registerLoading, setRegisterLoading] = useState(false)
  
  // 登录表单
  const [loginForm, setLoginForm] = useState({ username: '', password: '' })
  const [loginLoading, setLoginLoading] = useState(false)

  // 注册提交
  const handleRegister = async () => {
    if (!registerForm.username || registerForm.username.length < 2) {
      message.warning('用户名至少2个字符')
      return
    }
    if (!registerForm.password || registerForm.password.length < 6) {
      message.warning('密码至少6个字符')
      return
    }
    if (registerForm.password !== registerForm.confirmPassword) {
      message.warning('两次密码不一致')
      return
    }
    if (!registerForm.licenseKey) {
      message.warning('请输入卡密')
      return
    }
    
    setRegisterLoading(true)
    try {
      const r = await client.post('/auth/register', {
        username: registerForm.username,
        password: registerForm.password,
        license_key: registerForm.licenseKey,
      })
      if (r.data.success) {
        message.success('注册成功！正在登录...')
        // 自动登录
        login(r.data.access_token, r.data.username, r.data.role)
        navigate('/')
      } else {
        message.error(r.data.detail || '注册失败')
      }
    } catch (e: any) {
      message.error(e.response?.data?.detail || '注册失败，请检查卡密是否正确')
    }
    setRegisterLoading(false)
  }

  // 登录提交
  const handleLogin = async () => {
    if (!loginForm.username || !loginForm.password) {
      message.warning('请输入用户名和密码')
      return
    }
    
    setLoginLoading(true)
    try {
      const r = await client.post('/auth/login', {
        username: loginForm.username,
        password: loginForm.password,
      })
      if (r.data.success) {
        message.success('登录成功！')
        login(r.data.access_token, r.data.username, r.data.role)
        navigate('/')
      } else {
        message.error(r.data.detail || '登录失败')
      }
    } catch (e: any) {
      message.error(e.response?.data?.detail || '用户名或密码错误')
    }
    setLoginLoading(false)
  }

  const tabItems = [
    {
      key: 'register',
      label: <span><UserOutlined /> 注册账号</span>,
      children: (
        <div style={{ padding: '20px 0' }}>
          <Paragraph type="secondary" style={{ marginBottom: 24 }}>
            首次使用请注册账号，需要有效的卡密（向管理员获取）
          </Paragraph>
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Input
              prefix={<UserOutlined />}
              placeholder="用户名（至少2个字符）"
              value={registerForm.username}
              onChange={e => setRegisterForm({ ...registerForm, username: e.target.value })}
              size="large"
            />
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码（至少6个字符）"
              value={registerForm.password}
              onChange={e => setRegisterForm({ ...registerForm, password: e.target.value })}
              size="large"
            />
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="确认密码"
              value={registerForm.confirmPassword}
              onChange={e => setRegisterForm({ ...registerForm, confirmPassword: e.target.value })}
              size="large"
            />
            <Input
              prefix={<KeyOutlined />}
              placeholder="请输入卡密（如 XHS-XXXXXXXXXX）"
              value={registerForm.licenseKey}
              onChange={e => setRegisterForm({ ...registerForm, licenseKey: e.target.value.toUpperCase() })}
              size="large"
            />
            <Button
              type="primary"
              size="large"
              block
              loading={registerLoading}
              onClick={handleRegister}
            >
              注册并登录
            </Button>
          </Space>
        </div>
      ),
    },
    {
      key: 'login',
      label: <span><UserOutlined /> 用户登录</span>,
      children: (
        <div style={{ padding: '20px 0' }}>
          <Paragraph type="secondary" style={{ marginBottom: 24 }}>
            已有账号？请输入用户名和密码登录
          </Paragraph>
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Input
              prefix={<UserOutlined />}
              placeholder="用户名"
              value={loginForm.username}
              onChange={e => setLoginForm({ ...loginForm, username: e.target.value })}
              size="large"
            />
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
              value={loginForm.password}
              onChange={e => setLoginForm({ ...loginForm, password: e.target.value })}
              size="large"
              onPressEnter={handleLogin}
            />
            <Button
              type="primary"
              size="large"
              block
              loading={loginLoading}
              onClick={handleLogin}
            >
              登录
            </Button>
          </Space>
        </div>
      ),
    },
    {
      key: 'cookie',
      label: <span><LockOutlined /> Cookie登录</span>,
      children: (
        <CookieLoginTab />
      ),
    },
  ]

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #fff5f5 0%, #fff 50%, #f6ffed 100%)',
    }}>
      <Card style={{
        width: 480,
        boxShadow: '0 8px 24px rgba(0,0,0,0.08)',
        borderRadius: 12,
      }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Title level={3} style={{ margin: 0 }}>🥔 土豆小红书助手</Title>
          <Text type="secondary">注册/登录后开始使用</Text>
        </div>
        <Tabs items={tabItems} centered defaultActiveKey="register" />
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            注册/登录后即表示您同意使用条款
          </Text>
        </div>
      </Card>
    </div>
  )
}

// ── Cookie 登录 Tab（保留原有功能）──────────────────────────────────────
function CookieLoginTab() {
  const { message } = App.useApp()
  const [cookieText, setCookieText] = useState('')
  const [cookieSaving, setCookieSaving] = useState(false)

  const saveCookie = async () => {
    if (!cookieText.trim()) { message.warning('请输入Cookie'); return }
    setCookieSaving(true)
    try {
      await client.post('/config', { cookies: cookieText.trim() })
      const test = await client.post('/config/test-cookie')
      if (test.data.success) {
        message.success(test.data.message)
      } else {
        message.warning('Cookie已保存，但测试未通过：' + test.data.message)
      }
      // 跳转到首页
      window.location.href = '/'
    } catch (e: any) {
      message.error(e.response?.data?.message || '保存失败')
    }
    setCookieSaving(false)
  }

  return (
    <div style={{ padding: '20px 0' }}>
      <Alert
        type="info"
        showIcon
        message="Cookie 登录（备用方式）"
        description="如果您已有小红书Cookie，可以直接粘贴登录，无需注册"
        style={{ marginBottom: 16, textAlign: 'left' }}
      />
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <Paragraph type="secondary" style={{ fontSize: 12 }}>
          从浏览器开发者工具 (F12 → Network → 找到 xiaohongshu.com 请求 → Headers → Cookie) 复制完整的 Cookie 字符串
        </Paragraph>
        <Input.TextArea
          rows={6}
          value={cookieText}
          onChange={e => setCookieText(e.target.value)}
          placeholder="粘贴完整的Cookie字符串（如 a1=xxx; webId=xxx; web_session=xxx ...）"
          style={{ fontFamily: 'monospace', fontSize: 12 }}
        />
        <Button
          type="primary"
          block
          size="large"
          loading={cookieSaving}
          onClick={saveCookie}
          icon={<LockOutlined />}
        >
          保存Cookie并登录
        </Button>
      </Space>
    </div>
  )
}
