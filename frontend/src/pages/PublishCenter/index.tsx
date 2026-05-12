import React, { useEffect, useState } from 'react'
import { Card, Table, Button, Space, Typography, Tag, Modal, Form, Input, DatePicker, message, Popconfirm } from 'antd'
import { PlusOutlined, StopOutlined, ReloadOutlined } from '@ant-design/icons'
import client from '../../api/client'
import dayjs from 'dayjs'

const { Title } = Typography

export default function PublishCenterPage() {
  const [tasks, setTasks] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const r = await client.get('/publish', { params: { page } })
      setTasks(r.data.data || [])
      setTotal(r.data.total || 0)
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [page])

  const onCreate = async (values: any) => {
    try {
      const payload = { ...values }
      if (values.scheduled_at) {
        payload.scheduled_at = values.scheduled_at.toISOString()
      }
      await client.post('/publish', payload)
      message.success('发布任务已创建')
      setModalOpen(false)
      form.resetFields()
      load()
    } catch (e: any) {
      message.error('创建发布任务失败: ' + (e.response?.data?.message || e.message || '未知错误'))
    }
  }

  const onCancel = async (id: number) => {
    try {
      await client.post('/publish/cancel', { task_id: id })
      message.success('已取消')
      load()
    } catch (e: any) {
      message.error('取消失败: ' + (e.response?.data?.message || e.message || '未知错误'))
    }
  }

  const onRetry = async (id: number) => {
    try {
      await client.post(`/publish/retry/${id}`)
      message.success('重试中')
      load()
    } catch (e: any) {
      message.error('重试失败: ' + (e.response?.data?.message || e.message || '未知错误'))
    }
  }

  const statusMap: Record<string, { color: string; text: string }> = {
    pending: { color: 'orange', text: '排队中' },
    running: { color: 'blue', text: '发布中' },
    success: { color: 'green', text: '成功' },
    failed: { color: 'red', text: '失败' },
    cancelled: { color: 'default', text: '已取消' },
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>发布中心</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新建发布</Button>
        </Space>
      </div>
      <Card>
        <Table dataSource={tasks} rowKey="id" loading={loading} pagination={{ total, current: page, onChange: setPage }}
          columns={[
            { title: 'ID', dataIndex: 'id', width: 60 },
            { title: '标题', dataIndex: 'title', ellipsis: true },
            { title: '状态', dataIndex: 'status', width: 100, render: (v: string) => {
              const s = statusMap[v] || { color: 'default', text: v }
              return <Tag color={s.color}>{s.text}</Tag>
            }},
            { title: '定时', dataIndex: 'scheduled_at', width: 160, render: (v: string) => v || '即时' },
            { title: '发布时间', dataIndex: 'published_at', width: 160, render: (v: string) => v || '-' },
            { title: '操作', width: 150, render: (_: any, r: any) => (
              <Space>
                {r.status === 'pending' && <Button size="small" danger icon={<StopOutlined />} onClick={() => onCancel(r.id)}>取消</Button>}
                {r.status === 'failed' && <Button size="small" onClick={() => onRetry(r.id)}>重试</Button>}
              </Space>
            )},
          ]} />
      </Card>
      <Modal title="新建发布任务" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()}>
        <Form form={form} onFinish={onCreate} layout="vertical">
          <Form.Item name="title" label="标题" rules={[{ required: true }]}>
            <Input placeholder="笔记标题" />
          </Form.Item>
          <Form.Item name="content" label="正文">
            <Input.TextArea rows={6} placeholder="笔记正文内容..." />
          </Form.Item>
          <Form.Item name="images_json" label="图片URL（JSON数组）">
            <Input placeholder='["https://..."]' />
          </Form.Item>
          <Form.Item name="scheduled_at" label="定时发布（留空=即时）">
            <DatePicker showTime format="YYYY-MM-DD HH:mm" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="privacy" label="可见范围" initialValue="public">
            <Input placeholder="public / private" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
