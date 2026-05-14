import React, { useState, useEffect } from 'react'
import { Card, Typography, Table, Button, Space, Modal, Form, Input, Select, message, Popconfirm, Tag, Switch } from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text } = Typography

interface User {
  id: number
  username: string
  role: string
  is_active: boolean
  created_at: string
  last_login: string
}

export default function UserManagePage() {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [form] = Form.useForm()

  const loadUsers = async () => {
    setLoading(true)
    try {
      const r = await client.get('/admin/users')
      if (r.data.success) setUsers(r.data.data.items || r.data.data)
    } catch (e: any) {
      message.error('加载失败：' + (e.response?.data?.message || e.message))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadUsers() }, [])

  const onFinish = async (values: any) => {
    try {
      if (editingUser) {
        await client.put(`/admin/users/${editingUser.id}`, values)
        message.success('更新成功')
      } else {
        await client.post('/admin/users', values)
        message.success('创建成功')
      }
      setModalOpen(false)
      form.resetFields()
      loadUsers()
    } catch (e: any) {
      message.error('操作失败：' + (e.response?.data?.message || e.message))
    }
  }

  const toggleActive = async (user: User) => {
    try {
      await client.put(`/admin/users/${user.id}`, { is_active: !user.is_active })
      message.success('操作成功')
      loadUsers()
    } catch (e: any) {
      message.error('操作失败：' + (e.response?.data?.message || e.message))
    }
  }

  const deleteUser = async (id: number) => {
    try {
      await client.delete(`/admin/users/${id}`)
      message.success('删除成功')
      loadUsers()
    } catch (e: any) {
      message.error('删除失败：' + (e.response?.data?.message || e.message))
    }
  }

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>👥 用户管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadUsers}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingUser(null); form.resetFields(); setModalOpen(true) }}>新建用户</Button>
        </Space>
      </div>
      <Card>
        <Table
          rowKey="id"
          dataSource={users}
          loading={loading}
          columns={[
            { title: 'ID', dataIndex: 'id' },
            { title: '用户名', dataIndex: 'username' },
            { title: '角色', dataIndex: 'role', render: (r: string) => <Tag color={r === 'admin' ? 'red' : 'blue'}>{r}</Tag> },
            { title: '状态', render: (_, r) => <Switch checked={r.is_active} onChange={() => toggleActive(r)} checkedChildren="启用" unCheckedChildren="禁用" /> },
            { title: '创建时间', dataIndex: 'created_at' },
            { title: '最后登录', dataIndex: 'last_login', render: (t: string) => t ? new Date(t).toLocaleString('zh-CN') : '从未登录' },
            { title: '操作', render: (_, r) => (
              <Space>
                <Button size="small" onClick={() => { setEditingUser(r); form.setFieldsValue(r); setModalOpen(true) }}>编辑</Button>
                <Popconfirm title="确认删除？" onConfirm={() => deleteUser(r.id)}>
                  <Button size="small" danger>删除</Button>
                </Popconfirm>
              </Space>
            ) },
          ]}
        />
      </Card>
      <Modal
        title={editingUser ? '编辑用户' : '新建用户'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} onFinish={onFinish} layout="vertical">
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}> <Input /> </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: !editingUser }]}> <Input.Password placeholder={editingUser ? '留空表示不修改' : ''} /> </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true }]}> 
            <Select options={[{ label: '普通用户', value: 'user' }, { label: '管理员', value: 'admin' }]} /> 
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
