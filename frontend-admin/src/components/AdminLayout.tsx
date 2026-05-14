import React from 'react'
import { Layout, Menu, Button, Typography, Dropdown, theme } from 'antd'
import {
  DashboardOutlined,
  UserOutlined,
  KeyOutlined,
  RobotOutlined,
  FileTextOutlined,
  BarChartOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  NotificationOutlined,
} from '@ant-design/icons'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'

const { Header, Sider, Content } = Layout
const { Text } = Typography

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '系统概览' },
  { key: '/users', icon: <UserOutlined />, label: '用户管理' },
  { key: '/cards', icon: <KeyOutlined />, label: '卡密管理' },
  { key: '/announcements', icon: <NotificationOutlined />, label: '公告管理' },
  { key: '/ai-model', icon: <RobotOutlined />, label: 'AI 模型配置' },
  { key: '/logs', icon: <FileTextOutlined />, label: '系统日志' },
  { key: '/stats', icon: <BarChartOutlined />, label: '使用统计' },
]

export default function AdminLayout() {
  const [collapsed, setCollapsed] = React.useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { username, role, logout } = useAuthStore()
  const { token: themeToken } = theme.useToken()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // 计算当前选中菜单项
  const selectedKey = menuItems.find(
    item => item.key !== '/' && location.pathname.startsWith(item.key)
  )?.key || '/'

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        theme="light"
        width={220}
        style={{
          borderRight: `1px solid ${themeToken.colorBorderSecondary}`,
          boxShadow: '2px 0 8px rgba(0,0,0,0.06)',
        }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
            padding: '0 16px',
          }}
        >
          {collapsed ? (
            <span style={{ fontSize: 24 }}>🥔</span>
          ) : (
            <Text strong style={{ fontSize: 16, whiteSpace: 'nowrap' }}>
              🥔 土豆助手管理
            </Text>
          )}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderRight: 0, marginTop: 8 }}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            padding: '0 24px',
            background: themeToken.colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
            height: 64,
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{ fontSize: 16, width: 40, height: 40 }}
          />
          <Dropdown
            menu={{
              items: [
                {
                  key: 'info',
                  label: `${username}（${role === 'admin' ? '管理员' : '用户'}）`,
                  disabled: true,
                },
                { type: 'divider' },
                {
                  key: 'logout',
                  icon: <LogoutOutlined />,
                  label: '退出登录',
                  onClick: handleLogout,
                },
              ],
            }}
          >
            <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              <UserOutlined style={{ fontSize: 16 }} />
              <Text>{username}</Text>
            </div>
          </Dropdown>
        </Header>
        <Content
          style={{
            margin: 0,
            padding: 0,
            minHeight: 280,
            background: themeToken.colorBgLayout,
            overflow: 'auto',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
