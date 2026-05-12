import React, { useState, useEffect, useCallback } from 'react'
import { Layout, Menu, Avatar, Space, Badge, theme, Typography, Popover, Button, List, Tag, Empty, Dropdown } from 'antd'
import {
  DashboardOutlined, TeamOutlined, SearchOutlined, BookOutlined,
  PictureOutlined, SendOutlined, ThunderboltOutlined,
  EyeOutlined, SettingOutlined, BugOutlined,
  BellOutlined, UserOutlined, RobotOutlined, RocketOutlined,
  CheckOutlined, SafetyCertificateOutlined, FileTextOutlined, BulbOutlined,
  UserSwitchOutlined, LogoutOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import client from '../../api/client'

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
      { key: '/topics', icon: <BulbOutlined />, label: '选题推荐' },
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
      { key: '/content-check', icon: <SafetyCertificateOutlined />, label: '内容检测' },
      { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
      { key: '/logs', icon: <FileTextOutlined />, label: '运行日志' },
    ],
  },
]

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { token: { colorBgContainer } } = theme.useToken()

  // ── Notification state ──────────────────────────────────────────────────
  const [unreadCount, setUnreadCount] = useState(0)
  const [notifications, setNotifications] = useState<any[]>([])
  const [notiLoading, setNotiLoading] = useState(false)
  const [notiPopoverOpen, setNotiPopoverOpen] = useState(false)

  const fetchUnreadCount = useCallback(async () => {
    try {
      const r = await client.get('/notifications', { params: { page: 1, page_size: 1 } })
      if (r.data.success) setUnreadCount(r.data.unread || 0)
    } catch {}
  }, [])

  const fetchNotifications = useCallback(async () => {
    setNotiLoading(true)
    try {
      const r = await client.get('/notifications', { params: { page: 1, page_size: 10 } })
      if (r.data.success) setNotifications(r.data.data || [])
    } catch {}
    setNotiLoading(false)
  }, [])

  const markAsRead = useCallback(async (id: number) => {
    try {
      await client.post(`/notifications/${id}/read`)
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n))
      setUnreadCount(prev => Math.max(0, prev - 1))
    } catch {}
  }, [])

  const markAllRead = useCallback(async () => {
    try {
      await client.post('/notifications/read-all')
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })))
      setUnreadCount(0)
    } catch {}
  }, [])

  // Poll unread count every 30 seconds
  useEffect(() => {
    fetchUnreadCount()
    const timer = setInterval(fetchUnreadCount, 30000)
    return () => clearInterval(timer)
  }, [fetchUnreadCount])

  const onNotiPopoverOpen = (open: boolean) => {
    setNotiPopoverOpen(open)
    if (open) fetchNotifications()
  }

  const notiTypeColor: Record<string, string> = {
    info: 'blue', success: 'green', warning: 'orange', error: 'red', task: 'purple',
  }

  const notificationContent = (
    <div style={{ width: 360 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <Typography.Text strong>通知</Typography.Text>
        {unreadCount > 0 && (
          <Button type="link" size="small" icon={<CheckOutlined />} onClick={markAllRead}>
            全部已读
          </Button>
        )}
      </div>
      {notifications.length === 0 ? (
        <Empty description="暂无通知" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <List
          loading={notiLoading}
          dataSource={notifications}
          size="small"
          renderItem={(item: any) => (
            <List.Item
              style={{ opacity: item.is_read ? 0.6 : 1, cursor: 'pointer', padding: '8px 0' }}
              onClick={() => !item.is_read && markAsRead(item.id)}
            >
              <List.Item.Meta
                title={
                  <Space>
                    <Tag color={notiTypeColor[item.noti_type] || 'blue'} style={{ marginRight: 4 }}>
                      {item.noti_type || 'info'}
                    </Tag>
                    <Typography.Text strong={!item.is_read}>{item.title}</Typography.Text>
                  </Space>
                }
                description={
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {item.message}
                    {item.created_at && <span style={{ marginLeft: 8 }}>{item.created_at.slice(0, 16)}</span>}
                  </Typography.Text>
                }
              />
            </List.Item>
          )}
        />
      )}
    </div>
  )

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
            <Popover content={notificationContent} trigger="click" placement="bottomRight"
              open={notiPopoverOpen} onOpenChange={onNotiPopoverOpen}>
              <Badge count={unreadCount} size="small" offset={[-2, 2]}>
                <BellOutlined style={{ fontSize: 18, cursor: 'pointer' }} />
              </Badge>
            </Popover>
            <Dropdown
              menu={{
                items: [
                  {
                    key: 'user-center',
                    icon: <UserSwitchOutlined />,
                    label: '用户中心',
                  },
                  { type: 'divider' },
                  {
                    key: 'logout',
                    icon: <LogoutOutlined />,
                    label: '退出登录',
                    danger: true,
                  },
                ],
                onClick: ({ key }) => {
                  if (key === 'user-center') {
                    navigate('/user-center')
                  } else if (key === 'logout') {
                    localStorage.removeItem('xhs_cookie_configured')
                    navigate('/login')
                  }
                },
              }}
              trigger={['click']}
              placement="bottomRight"
            >
              <Space style={{ cursor: 'pointer' }}>
                <Avatar size="small" icon={<UserOutlined />} />
                <span>Admin</span>
              </Space>
            </Dropdown>
          </Space>
        </Header>
        <Content style={{ margin: 16, padding: 24, background: colorBgContainer, borderRadius: 8, minHeight: 280 }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  )
}
