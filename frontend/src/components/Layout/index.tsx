import React, { useState } from 'react'
import { Layout, Menu, Avatar, Space, Badge, theme, Typography } from 'antd'
import {
  DashboardOutlined, TeamOutlined, SearchOutlined, BookOutlined,
  PictureOutlined, SendOutlined, ThunderboltOutlined,
  EyeOutlined, SettingOutlined, BugOutlined,
  BellOutlined, UserOutlined, RobotOutlined, RocketOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'

const { Header, Sider, Content } = Layout

const menuItems = [
  {
    key: 'workspace',
    label: '工作台',
    type: 'group' as const,
    children: [
      { key: '/', icon: <RocketOutlined />, label: '一站式工作台' },
      { key: '/dashboard', icon: <DashboardOutlined />, label: '今日看板' },
    ],
  },
  {
    key: 'discover',
    label: '找内容',
    type: 'group' as const,
    children: [
      { key: '/discovery', icon: <SearchOutlined />, label: '热门发现' },
      { key: '/kol', icon: <RobotOutlined />, label: 'KOL搜索' },
      { key: '/monitor', icon: <EyeOutlined />, label: '竞品监控' },
    ],
  },
  {
    key: 'create',
    label: '做内容',
    type: 'group' as const,
    children: [
      { key: '/content', icon: <BookOutlined />, label: '我的内容' },
      { key: '/images', icon: <PictureOutlined />, label: '图片工作台' },
    ],
  },
  {
    key: 'publish',
    label: '发内容',
    type: 'group' as const,
    children: [
      { key: '/publish', icon: <SendOutlined />, label: '发布中心' },
      { key: '/automation', icon: <ThunderboltOutlined />, label: '定时发布' },
    ],
  },
  {
    key: 'system',
    label: '系统',
    type: 'group' as const,
    children: [
      { key: '/accounts', icon: <TeamOutlined />, label: '账号管理' },
      { key: '/anti-crawl', icon: <BugOutlined />, label: '反爬配置' },
      { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
    ],
  },
]

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { token: { colorBgContainer } } = theme.useToken()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}
        theme="light" style={{ borderRight: '1px solid #f0f0f0' }}>
        <div style={{ height: 48, margin: 12, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontSize: collapsed ? 18 : 16, fontWeight: 700, color: '#ff4757' }}>
            {collapsed ? '🥔' : '🥔 土豆小红书助手'}
          </span>
        </div>
        <Menu mode="inline" selectedKeys={[location.pathname]}
          items={menuItems} onClick={({ key }) => navigate(key)} />
      </Sider>
      <Layout>
        <Header style={{ background: colorBgContainer, padding: '0 24px',
          display: 'flex', alignItems: 'center', justifyContent: 'flex-end',
          borderBottom: '1px solid #f0f0f0' }}>
          <Space size="middle">
            <Badge count={0} size="small">
              <BellOutlined style={{ fontSize: 18, cursor: 'pointer' }} />
            </Badge>
            <Space style={{ cursor: 'pointer' }}>
              <Avatar size="small" icon={<UserOutlined />} />
              <span>Admin</span>
            </Space>
          </Space>
        </Header>
        <Content style={{ margin: 16, padding: 24, background: colorBgContainer, borderRadius: 8, minHeight: 280 }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  )
}
