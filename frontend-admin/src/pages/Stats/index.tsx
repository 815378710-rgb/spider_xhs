import React, { useState, useEffect } from 'react'
import { Card, Typography, Table, DatePicker, Space, Select, Tag, Button, message, Spin } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import client from '../../api/client'
import type { ColumnsType } from 'antd/es/table'

const { Title, Text } = Typography
const { RangePicker } = DatePicker

interface UserStats {
  username: string
  role: string
  api_calls: number
  token_usage: number
  last_active: string
}

export default function StatsPage() {
  const [stats, setStats] = useState<UserStats[]>([])
  const [loading, setLoading] = useState(false)
  const [dateRange, setDateRange] = useState<any>(null)
  const [groupBy, setGroupBy] = useState<string>('user')

  const loadStats = async () => {
    setLoading(true)
    try {
      const params: any = { group_by: groupBy }
      if (dateRange) {
        params.start_date = dateRange[0].format('YYYY-MM-DD')
        params.end_date = dateRange[1].format('YYYY-MM-DD')
      }
      const r = await client.get('/admin/stats/usage', { params })
      if (r.data.success) setStats(r.data.data)
    } catch (e: any) {
      message.error('加载失败：' + (e.response?.data?.message || e.message))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadStats() }, [groupBy])

  const columns: ColumnsType<UserStats> = [
    { title: '用户名', dataIndex: 'username' },
    { title: '角色', dataIndex: 'role', render: (r: string) => <Tag color={r === 'admin' ? 'red' : 'blue'}>{r}</Tag> },
    { title: 'API调用次数', dataIndex: 'api_calls', sorter: (a, b) => a.api_calls - b.api_calls },
    { title: 'Token消耗', dataIndex: 'token_usage', sorter: (a, b) => a.token_usage - b.token_usage,
      render: (v: number) => v >= 10000 ? (v / 10000).toFixed(1) + '万' : v },
    { title: '最后活跃', dataIndex: 'last_active' },
  ]

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>📊 使用统计</Title>
        <Space>
          <RangePicker onChange={setDateRange} />
          <Select value={groupBy} onChange={setGroupBy} style={{ width: 120 }}
            options={[{ label: '按用户', value: 'user' }, { label: '按日期', value: 'date' }]} />
          <Button icon={<ReloadOutlined />} onClick={loadStats}>刷新</Button>
        </Space>
      </div>
      <Card>
        <Table
          rowKey="username"
          dataSource={stats}
          columns={columns}
          loading={loading}
          pagination={{ pageSize: 20 }}
          summary={pageData => {
            let totalCalls = 0, totalTokens = 0
            pageData.forEach(({ api_calls, token_usage }) => { totalCalls += api_calls; totalTokens += token_usage })
            return (
              <Table.Summary fixed>
                <Table.Summary.Row>
                  <Table.Summary.Cell index={0}>合计</Table.Summary.Cell>
                  <Table.Summary.Cell index={1}>-</Table.Summary.Cell>
                  <Table.Summary.Cell index={2}>{totalCalls}</Table.Summary.Cell>
                  <Table.Summary.Cell index={3}>{totalTokens >= 10000 ? (totalTokens / 10000).toFixed(1) + '万' : totalTokens}</Table.Summary.Cell>
                  <Table.Summary.Cell index={4}>-</Table.Summary.Cell>
                </Table.Summary.Row>
              </Table.Summary>
            )
          }}
        />
      </Card>
    </div>
  )
}
