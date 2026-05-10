import React, { useEffect, useState } from 'react'
import { Card, Table, Button, Tag, Space, Modal, Form, Input, Select, message, Typography, Popconfirm } from 'antd'
import { PlusOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title } = Typography

export default function AccountMatrixPage() {
  const [accounts, setAccounts] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const r = await client.get('/accounts')
      setAccounts(r.data.data || [])
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const onAdd = async (values: any) => {
    try {
      await client.post('/accounts', values)
      message.success('账号已添加')
      setModalOpen(false)
      form.resetFields()
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '添加失败')
    }
  }

  const onDelete = async (id: number) => {
    await client.delete(`/accounts/${id}`)
    message.success('已删除')
    load()
  }

  const onCheck = async (id: number) => {
    const r = await client.post(`/accounts/${id}/check`)
    if (r.data.success) message.success(r.data.message)
    else message.warning(r.data.message)
    load()
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>账号矩阵</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>添加账号</Button>
        </Space>
      </div>
      <Card>
        <Table dataSource={accounts} rowKey="id" loading={loading}
          columns={[
            { title: 'ID', dataIndex: 'id', width: 60 },
            { title: '平台', dataIndex: 'platform', width: 80, render: (v: string) => <Tag>{v}</Tag> },
            { title: '昵称', dataIndex: 'nickname' },
            { title: '状态', dataIndex: 'status', render: (v: string) =>
              <Tag color={v === 'active' ? 'green' : v === 'expired' ? 'orange' : 'red'}>{v}</Tag> },
            { title: '上次检查', dataIndex: 'last_check', render: (v: string) => v || '-' },
            { title: '操作', render: (_: any, r: any) => (
              <Space>
                <Button size="small" onClick={() => onCheck(r.id)}>健康检查</Button>
                <Popconfirm title="确定删除？" onConfirm={() => onDelete(r.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            )},
          ]} />
      </Card>
      <Modal title="添加账号" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()}>
        <Form form={form} onFinish={onAdd} layout="vertical">
          <Form.Item name="platform" label="平台" initialValue="xhs">
            <Select options={[{ value: 'xhs', label: '小红书PC' }, { value: 'creator', label: '创作者平台' }]} />
          </Form.Item>
          <Form.Item name="nickname" label="昵称">
            <Input placeholder="可选" />
          </Form.Item>
          <Form.Item name="cookies" label="Cookie">
            <Input.TextArea rows={4} placeholder="粘贴完整的Cookie字符串" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
