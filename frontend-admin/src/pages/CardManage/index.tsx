import React, { useState, useEffect } from 'react'
import { Card, Typography, Table, Button, Space, Modal, Form, Input, Select, message, Tag, Popconfirm, Typography as Typo } from 'antd'
import { PlusOutlined, ReloadOutlined, CopyOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text } = Typography

interface Card {
  id: number
  code: string
  role: string
  is_used: boolean
  used_by: number | null
  used_by_username: string
  created_at: string
  expires_at: string
}

export default function CardManagePage() {
  const [cards, setCards] = useState<Card[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const loadCards = async () => {
    setLoading(true)
    try {
      const r = await client.get('/admin/license-keys')
      if (r.data.success) setCards(r.data.data.items || r.data.data)
    } catch (e: any) {
      message.error('加载失败：' + (e.response?.data?.message || e.message))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadCards() }, [])

  const onFinish = async (values: any) => {
    try {
      await client.post('/admin/license-keys', values)
      message.success(`成功生成 ${values.count} 张卡密`)
      setModalOpen(false)
      form.resetFields()
      loadCards()
    } catch (e: any) {
      message.error('生成失败：' + (e.response?.data?.message || e.message))
    }
  }

  const copyCode = (code: string) => {
    navigator.clipboard.writeText(code)
    message.success('已复制')
  }

  const deleteCard = async (id: number) => {
    try {
      await client.delete(`/admin/license-keys/${id}`)
      message.success('删除成功')
      loadCards()
    } catch (e: any) {
      message.error('删除失败：' + (e.response?.data?.message || e.message))
    }
  }

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>🔑 卡密管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadCards}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setModalOpen(true) }}>批量生成</Button>
        </Space>
      </div>
      <Card>
        <Table
          rowKey="id"
          dataSource={cards}
          loading={loading}
          columns={[
            { title: 'ID', dataIndex: 'id' },
            { title: '卡密', dataIndex: 'code', render: (c: string) => <Space><Text code>{c}</Text><Button size="small" icon={<CopyOutlined />} onClick={() => copyCode(c)} /></Space> },
            { title: '角色', dataIndex: 'role', render: (r: string) => <Tag color={r === 'admin' ? 'red' : 'blue'}>{r}</Tag> },
            { title: '状态', render: (_: any, r: Card) => r.is_used ? <Tag color="red">已使用</Tag> : <Tag color="green">未使用</Tag> },
            { title: '使用者', render: (_: any, r: Card) => r.used_by_username || (r.used_by ? `用户#${r.used_by}（已删除）` : '-') },
            { title: '创建时间', dataIndex: 'created_at' },
            { title: '过期时间', dataIndex: 'expires_at' },
            { title: '操作', render: (_: any, r: Card) => (
              <Popconfirm title="确认删除？" onConfirm={() => deleteCard(r.id)}>
                <Button size="small" danger disabled={r.is_used}>删除</Button>
              </Popconfirm>
            ) },
          ]}
        />
      </Card>
      <Modal title="批量生成卡密" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()}>
        <Form form={form} onFinish={onFinish} layout="vertical">
          <Form.Item name="count" label="生成数量" rules={[{ required: true }]} initialValue={1}> <Input type="number" min={1} max={100} /> </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true }]}> 
            <Select options={[{ label: '普通用户', value: 'user' }, { label: '管理员', value: 'admin' }]} /> 
          </Form.Item>
          <Form.Item name="expires_days" label="有效期（天，0表示永久）" initialValue={365}> <Input type="number" min={0} /> </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
