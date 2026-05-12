import React, { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic, Typography, Tag, Button, Space, List, Empty, Divider } from 'antd'
import {
  FileTextOutlined, SendOutlined, CheckCircleOutlined, ClockCircleOutlined,
  RocketOutlined, SearchOutlined, ArrowRightOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { Line, Pie } from '@ant-design/charts'
import client from '../../api/client'

const { Title, Text, Paragraph } = Typography

export default function DashboardPage() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<any>({})
  const [recentNotes, setRecentNotes] = useState<any[]>([])
  const [pendingTasks, setPendingTasks] = useState<any[]>([])
  const [trendData, setTrendData] = useState<any>({})
  const [categoryData, setCategoryData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const [dashRes, notesRes, publishRes, trendRes, catRes] = await Promise.allSettled([
          client.get('/analytics/dashboard'),
          client.get('/content', { params: { page: 1 } }),
          client.get('/publish', { params: { page: 1 } }),
          client.get('/analytics/trend', { params: { days: 7 } }),
          client.get('/analytics/category-dist'),
        ])
        if (dashRes.status === 'fulfilled') setStats(dashRes.value.data?.data || {})
        if (notesRes.status === 'fulfilled') setRecentNotes(notesRes.value.data?.data?.slice(0, 5) || [])
        if (publishRes.status === 'fulfilled') setPendingTasks(publishRes.value.data?.data?.slice(0, 5) || [])
        if (trendRes.status === 'fulfilled') setTrendData(trendRes.value.data?.data || {})
        if (catRes.status === 'fulfilled') setCategoryData(catRes.value.data?.data || [])
      } catch {}
      setLoading(false)
    }
    load()
  }, [])

  const statCards = [
    {
      title: '今日已采集',
      value: stats.total_notes || 0,
      icon: <FileTextOutlined />,
      color: '#ff4757',
      sub: '篇笔记',
    },
    {
      title: '待发布',
      value: stats.pending_publish || 0,
      icon: <ClockCircleOutlined />,
      color: '#faad14',
      sub: '篇草稿',
    },
    {
      title: '已发布',
      value: stats.success_publish || 0,
      icon: <SendOutlined />,
      color: '#52c41a',
      sub: '篇',
    },
    {
      title: '成功率',
      value: stats.publish_rate || '0%',
      icon: <CheckCircleOutlined />,
      color: '#1890ff',
      sub: '',
    },
  ]

  const statusMap: Record<string, { color: string; text: string }> = {
    pending: { color: 'orange', text: '排队中' },
    running: { color: 'blue', text: '发布中' },
    success: { color: 'green', text: '成功' },
    failed: { color: 'red', text: '失败' },
    cancelled: { color: 'default', text: '已取消' },
  }

  // Prepare Line chart data
  const lineData = trendData.labels?.map((label: string, i: number) => [
    { date: label, value: trendData.collect[i], category: '采集' },
    { date: label, value: trendData.publish[i], category: '发布' },
  ]).flat() || []

  // Prepare Pie chart data
  const pieData = categoryData.map((d: any) => ({
    type: d.type === 'video' ? '视频' : '图文',
    value: d.count,
  }))

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>👋 今日工作台</Title>
        <Text type="secondary">管理你的小红书内容创作流程</Text>
      </div>

      {/* 快捷操作 */}
      <Card style={{ marginBottom: 24, background: 'linear-gradient(135deg, #fff5f5 0%, #fff 100%)' }}>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <Text strong style={{ fontSize: 16 }}>🚀 快速开始</Text>
            <Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
              粘贴小红书链接，一键完成采集 → AI改写 → 图片降重 → 发布
            </Paragraph>
          </Col>
          <Col>
            <Space>
              <Button type="primary" size="large" icon={<RocketOutlined />}
                onClick={() => navigate('/')}>
                一键工作台
              </Button>
              <Button size="large" icon={<SearchOutlined />}
                onClick={() => navigate('/discovery')}>
                热门发现
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        {statCards.map((s, i) => (
          <Col span={6} key={i}>
            <Card hoverable>
              <Statistic title={s.title} value={s.value} prefix={s.icon}
                suffix={s.sub} valueStyle={{ color: s.color }} />
            </Card>
          </Col>
        ))}
      </Row>

      <Divider />

      {/* 数据图表 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={12}>
          <Card title="📈 近7天趋势">
            <Line
              data={lineData}
              xField="date"
              yField="value"
              colorField="category"
              height={280}
              point={{ size: 3 }}
              interaction={{
                tooltip: {
                  render: (e: any, { title, items }: any) => {
                    return `<div>${title}${items?.map((item: any) => `<br/>${item.name}: ${item.value}`).join('')}</div>`
                  },
                },
              }}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="📊 素材类型分布">
            <Pie
              data={pieData}
              angleField="value"
              colorField="type"
              height={280}
              innerRadius={0.5}
              label={{ text: 'type', position: 'outside' }}
              legend={{ position: 'bottom' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        {/* 最近采集 */}
        <Col span={12}>
          <Card title="📚 最近采集" extra={
            <Button type="link" size="small" onClick={() => navigate('/content')}>
              查看全部 <ArrowRightOutlined />
            </Button>
          }>
            {recentNotes.length > 0 ? (
              <List dataSource={recentNotes} renderItem={(item: any) => (
                <List.Item>
                  <List.Item.Meta
                    title={<Text ellipsis style={{ maxWidth: 300 }}>{item.title}</Text>}
                    description={<Text type="secondary">{item.author_name} · 👍 {item.likes || 0}</Text>}
                  />
                  <Button size="small" type="link"
                    onClick={() => { localStorage.setItem('edit_note', JSON.stringify(item)); navigate('/content') }}>
                    编辑
                  </Button>
                </List.Item>
              )} />
            ) : (
              <Empty description="暂无采集笔记" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>

        {/* 待发布任务 */}
        <Col span={12}>
          <Card title="📤 最近发布" extra={
            <Button type="link" size="small" onClick={() => navigate('/publish')}>
              查看全部 <ArrowRightOutlined />
            </Button>
          }>
            {pendingTasks.length > 0 ? (
              <List dataSource={pendingTasks} renderItem={(item: any) => (
                <List.Item>
                  <List.Item.Meta
                    title={<Text ellipsis style={{ maxWidth: 300 }}>{item.title}</Text>}
                    description={(() => {
                      const s = statusMap[item.status] || { color: 'default', text: item.status }
                      return <Tag color={s.color}>{s.text}</Tag>
                    })()}
                  />
                </List.Item>
              )} />
            ) : (
              <Empty description="暂无发布任务" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
