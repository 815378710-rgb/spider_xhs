import React, { useEffect, useState } from 'react'
import { Card, Typography, Row, Col, Statistic, Spin, message } from 'antd'
import { UserOutlined, KeyOutlined, ApiOutlined, RiseOutlined } from '@ant-design/icons'
import client from '../../api/client'
import { useNavigate } from 'react-router-dom'

const { Title, Text } = Typography

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => { loadStats() }, [])

  const loadStats = async () => {
    setLoading(true)
    try {
      const r = await client.get('/admin/stats')
      if (r.data.success) setStats(r.data.data)
    } catch (e: any) {
      message.error('加载失败：' + (e.response?.data?.message || e.message))
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>

  return (
    <div style={{ padding: 24 }}>
      <Title level={3} style={{ marginBottom: 24 }}>📊 系统概览</Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={6}>
          <Card hoverable onClick={() => navigate('/users')}>
            <Statistic title="总用户数" value={stats?.totalUsers || 0} prefix={<UserOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card hoverable onClick={() => navigate('/cards')}>
            <Statistic title="有效卡密" value={stats?.activeCards || 0} prefix={<KeyOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic title="今日API调用" value={stats?.todayApiCalls || 0} prefix={<ApiOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic title="Token消耗（今日）" value={stats?.todayTokenUsage || 0} prefix={<RiseOutlined />} />
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <Card title="📈 最近7天API调用趋势">
            <Text type="secondary">（图表组件待接入）</Text>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="🔥 活跃用户TOP10">
            <Text type="secondary">（列表组件待接入）</Text>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
