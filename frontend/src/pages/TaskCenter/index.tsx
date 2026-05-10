import React, { useEffect, useState } from 'react'
import { Card, Table, Tag, Typography, Select, Space, Button } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title } = Typography

export default function TaskCenterPage() {
  const [tasks, setTasks] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [typeFilter, setTypeFilter] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const r = await client.get('/tasks', { params: { page, task_type: typeFilter } })
      setTasks(r.data.data || [])
      setTotal(r.data.total || 0)
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [page, typeFilter])

  const statusColor: Record<string, string> = {
    running: 'blue', success: 'green', failed: 'red',
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>任务中心</Title>
        <Space>
          <Select placeholder="按类型筛选" allowClear style={{ width: 160 }}
            onChange={v => { setTypeFilter(v || ''); setPage(1) }}
            options={[
              { value: 'collect', label: '采集' }, { value: 'rewrite', label: '改写' },
              { value: 'publish', label: '发布' }, { value: 'automation', label: '自动化' },
            ]} />
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
        </Space>
      </div>
      <Card>
        <Table dataSource={tasks} rowKey="id" loading={loading}
          pagination={{ total, current: page, onChange: setPage }}
          columns={[
            { title: 'ID', dataIndex: 'id', width: 60 },
            { title: '类型', dataIndex: 'task_type', width: 100, render: (v: string) => <Tag>{v}</Tag> },
            { title: '状态', dataIndex: 'status', width: 100, render: (v: string) =>
              <Tag color={statusColor[v] || 'default'}>{v}</Tag> },
            { title: '详情', dataIndex: 'detail', ellipsis: true },
            { title: '耗时(秒)', dataIndex: 'duration_seconds', width: 100,
              render: (v: number) => v ? v.toFixed(1) : '-' },
            { title: '时间', dataIndex: 'created_at', width: 180 },
          ]} />
      </Card>
    </div>
  )
}
