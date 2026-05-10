import React, { useEffect, useState } from 'react'
import { Card, Table, Button, Space, Typography, Tag, Modal, Form, Input, Switch, message, Popconfirm } from 'antd'
import { PlusOutlined, PlayCircleOutlined, DeleteOutlined, PauseCircleOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title } = Typography

export default function AutomationPage() {
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const r = await client.get('/automation')
      setItems(r.data.data || [])
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const onCreate = async (values: any) => {
    await client.post('/automation', {
      name: values.name, keywords: values.keywords,
      schedule_cron: values.schedule_cron || '0 9 * * *',
    })
    message.success('流水线已创建')
    setModalOpen(false)
    form.resetFields()
    load()
  }

  const onToggle = async (id: number) => {
    await client.post(`/automation/${id}/toggle`)
    load()
  }

  const onRun = async (id: number) => {
    await client.post(`/automation/${id}/run`)
    message.success('已启动')
    load()
  }

  const onDelete = async (id: number) => {
    await client.delete(`/automation/${id}`)
    message.success('已删除')
    load()
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>定时发布</Title>
          <Typography.Text type="secondary">自动搜索关键词、采集改写并发布</Typography.Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新建定时任务</Button>
      </div>
      <Card>
        <Table dataSource={items} rowKey="id" loading={loading} pagination={false}
          columns={[
            { title: 'ID', dataIndex: 'id', width: 60 },
            { title: '名称', dataIndex: 'name' },
            { title: '关键词', dataIndex: 'keywords', ellipsis: true },
            { title: 'Cron', dataIndex: 'schedule_cron', width: 120 },
            { title: '状态', dataIndex: 'is_active', width: 80, render: (v: boolean) =>
              <Tag color={v ? 'green' : 'default'}>{v ? '运行中' : '已暂停'}</Tag> },
            { title: '运行次数', dataIndex: 'run_count', width: 80 },
            { title: '上次运行', dataIndex: 'last_check', width: 160, render: (v: string) => v || '-' },
            { title: '操作', width: 200, render: (_: any, r: any) => (
              <Space>
                <Button size="small" icon={<PlayCircleOutlined />} onClick={() => onRun(r.id)}>执行</Button>
                <Button size="small" icon={r.is_active ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                  onClick={() => onToggle(r.id)}>
                  {r.is_active ? '暂停' : '启用'}
                </Button>
                <Popconfirm title="确定删除？" onConfirm={() => onDelete(r.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            )},
          ]} />
      </Card>
      <Modal title="新建定时任务" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()}>
        <Form form={form} onFinish={onCreate} layout="vertical">
          <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
            <Input placeholder="例如：每日穿搭自动改写" />
          </Form.Item>
          <Form.Item name="keywords" label="搜索关键词（逗号分隔）" rules={[{ required: true }]}>
            <Input.TextArea rows={3} placeholder="穿搭分享, OOTD, 日常穿搭 ..." />
          </Form.Item>
          <Form.Item name="schedule_cron" label="执行时间（Cron表达式）" initialValue="0 9 * * *"
            extra="示例：每天9点=0 9 * * *，每周一10点=0 10 * * 1">
            <Input placeholder="0 9 * * * (每天9:00)" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
