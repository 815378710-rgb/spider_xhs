import React, { useEffect, useState } from 'react'
import { Card, Table, Button, Space, Typography, Tag, Modal, Form, Input, Select, message, Popconfirm, Drawer } from 'antd'
import { PlusOutlined, PlayCircleOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title } = Typography

export default function MonitorPage() {
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [snapDrawer, setSnapDrawer] = useState<any>(null)
  const [snapshots, setSnapshots] = useState<any[]>([])
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const r = await client.get('/monitor')
      setItems(r.data.data || [])
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const onCreate = async (values: any) => {
    await client.post('/monitor', values)
    message.success('监控已创建')
    setModalOpen(false)
    form.resetFields()
    load()
  }

  const onCheck = async (id: number) => {
    const r = await client.post(`/monitor/${id}/check`)
    if (r.data.success) message.success('检查完成')
    else message.warning(r.data.message)
    load()
  }

  const onViewSnaps = async (item: any) => {
    setSnapDrawer(item)
    const r = await client.get(`/monitor/${item.id}/snapshots`)
    setSnapshots(r.data.data || [])
  }

  const onDelete = async (id: number) => {
    await client.delete(`/monitor/${id}`)
    message.success('已删除')
    load()
  }

  const typeMap: Record<string, string> = { keyword: '关键词', account: '账号', brand: '品牌', url: 'URL' }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>竞品监控</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新建监控</Button>
      </div>
      <Card>
        <Table dataSource={items} rowKey="id" loading={loading} pagination={false}
          columns={[
            { title: 'ID', dataIndex: 'id', width: 60 },
            { title: '名称', dataIndex: 'name' },
            { title: '类型', dataIndex: 'monitor_type', width: 80, render: (v: string) => <Tag>{typeMap[v] || v}</Tag> },
            { title: '目标', dataIndex: 'target', ellipsis: true },
            { title: '间隔(分)', dataIndex: 'interval_minutes', width: 80 },
            { title: '状态', dataIndex: 'is_active', width: 80, render: (v: boolean) =>
              <Tag color={v ? 'green' : 'default'}>{v ? '运行中' : '暂停'}</Tag> },
            { title: '上次检查', dataIndex: 'last_check', width: 160, render: (v: string) => v || '-' },
            { title: '操作', width: 200, render: (_: any, r: any) => (
              <Space>
                <Button size="small" icon={<PlayCircleOutlined />} onClick={() => onCheck(r.id)}>检查</Button>
                <Button size="small" icon={<EyeOutlined />} onClick={() => onViewSnaps(r)}>快照</Button>
                <Popconfirm title="删除？" onConfirm={() => onDelete(r.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            )},
          ]} />
      </Card>
      <Modal title="新建监控" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()}>
        <Form form={form} onFinish={onCreate} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="监控名称" />
          </Form.Item>
          <Form.Item name="monitor_type" label="类型" initialValue="keyword">
            <Select options={[
              { value: 'keyword', label: '关键词' },
              { value: 'account', label: '账号' },
              { value: 'brand', label: '品牌' },
              { value: 'url', label: 'URL' },
            ]} />
          </Form.Item>
          <Form.Item name="target" label="目标" rules={[{ required: true }]}>
            <Input placeholder="关键词/用户ID/品牌名/URL" />
          </Form.Item>
          <Form.Item name="interval_minutes" label="检查间隔(分钟)" initialValue={60}>
            <Input type="number" />
          </Form.Item>
        </Form>
      </Modal>
      <Drawer title={`快照: ${snapDrawer?.name || ''}`} open={!!snapDrawer} onClose={() => setSnapDrawer(null)} width={600}>
        {snapshots.map((s, i) => (
          <Card key={s.id} size="small" style={{ marginBottom: 8 }}>
            <Typography.Text type="secondary">#{i + 1} — {s.created_at}</Typography.Text>
            <pre style={{ maxHeight: 200, overflow: 'auto', fontSize: 12 }}>{s.data_json}</pre>
          </Card>
        ))}
        {!snapshots.length && <Typography.Text type="secondary">暂无快照</Typography.Text>}
      </Drawer>
    </div>
  )
}
