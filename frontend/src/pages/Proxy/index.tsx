import React, { useState, useEffect } from 'react'
import { App,  Card, Typography, Alert, Button, Space, Tag, Table, Spin } from 'antd'
import { CloudServerOutlined, LinkOutlined, ReloadOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text, Paragraph } = Typography

interface ProxyRequest {
  request_id: string
  method: string
  url: string
  created_at?: number
}

export default function ProxyPage() {
  const [pendingCount, setPendingCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [recentRequests, setRecentRequests] = useState<ProxyRequest[]>([])

  const loadStatus = async () => {
    setLoading(true)
    try {
      // Try to get pending count (this endpoint might not be accessible to normal users)
      const r = await client.get('/proxy/pending')
      if (r.data.success && r.data.requests) {
        setPendingCount(r.data.requests.length)
        setRecentRequests(r.data.requests)
      }
    } catch (e: any) {
      // This endpoint might require special auth - that's ok
      console.log('Proxy status check:', e.response?.data || e.message)
    }
    setLoading(false)
  }

  useEffect(() => {
    loadStatus()
  }, [])

  const columns = [
    {
      title: '请求ID',
      dataIndex: 'request_id',
      key: 'request_id',
      ellipsis: true,
      width: 150,
    },
    {
      title: '方法',
      dataIndex: 'method',
      key: 'method',
      width: 80,
      render: (method: string) => <Tag color="blue">{method}</Tag>,
    },
    {
      title: 'URL',
      dataIndex: 'url',
      key: 'url',
      ellipsis: true,
      render: (url: string) => (
        <a href={url} target="_blank" rel="noopener noreferrer">{url}</a>
      ),
    },
  ]

  return (
    <div>
      <Title level={4}>浏览器代理</Title>
      <Paragraph type="secondary">
        通过 Chrome 扩展转发请求，绕过反爬虫限制
      </Paragraph>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
        message="使用说明"
        description={
          <div>
            <p>1. 安装配套的 Chrome 扩展（联系管理员获取）</p>
            <p>2. 扩展会自动轮询待处理的请求</p>
            <p>3. 在浏览器中执行请求并返回结果</p>
            <p>4. 查看 <a href="https://github.com/815378710-rgb/spider_xhs" target="_blank" rel="noopener noreferrer">文档</a> 了解更多信息</p>
          </div>
        }
      />

      <Space size="middle" style={{ marginBottom: 24 }}>
        <Card>
          <Tag color={pendingCount > 0 ? "orange" : "green"} style={{ padding: '8px 16px', fontSize: 16 }}>
            {pendingCount > 0 ? `待处理: ${pendingCount}` : '空闲'}
          </Tag>
        </Card>
        <Button icon={<ReloadOutlined />} onClick={loadStatus} loading={loading}>
          刷新状态
        </Button>
      </Space>

      {recentRequests.length > 0 && (
        <Card title="最近的请求">
          <Table
            columns={columns}
            dataSource={recentRequests}
            rowKey="request_id"
            pagination={false}
            size="small"
          />
        </Card>
      )}

      {recentRequests.length === 0 && !loading && (
        <Card>
          <Text type="secondary">暂无待处理的代理请求</Text>
        </Card>
      )}
    </div>
  )
}
