import React, { useState, useEffect, useCallback } from 'react'
import { Card, Tabs, Table, Button, Space, Input, Tag, Modal, Form, Switch, Select, message, Typography, Popconfirm, Row, Col, Statistic, Tooltip, InputNumber } from 'antd'
import { UserOutlined, KeyOutlined, NotificationOutlined, RobotOutlined, PlusOutlined, DeleteOutlined, CopyOutlined, SearchOutlined, ReloadOutlined, SettingOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text, Paragraph } = Typography

// ── User Management Tab ─────────────────────────────────────────────────────

function UserManagement() {
  const [users, setUsers] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [editModal, setEditModal] = useState<any>(null)
  const [editForm] = Form.useForm()

  const loadUsers = useCallback(async (p = page, s = search) => {
    setLoading(true)
    try {
      const r = await client.get('/admin/users', { params: { page: p, page_size: 15, search: s } })
      if (r.data.success) {
        setUsers(r.data.data.items)
        setTotal(r.data.data.total)
      }
    } catch { }
    setLoading(false)
  }, [page, search])

  useEffect(() => { loadUsers() }, [])

  const handleSearch = () => { setPage(1); loadUsers(1, search) }

  const handleToggleStatus = async (record: any) => {
    const newStatus = record.status === 'active' ? 'disabled' : 'active'
    try {
      await client.put(`/admin/users/${record.id}`, { status: newStatus })
      message.success(`用户已${newStatus === 'active' ? '启用' : '禁用'}`)
      loadUsers()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '操作失败')
    }
  }

  const handleDelete = async (record: any) => {
    try {
      await client.delete(`/admin/users/${record.id}`)
      message.success('用户已删除')
      loadUsers()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '删除失败')
    }
  }

  const handleEdit = (record: any) => {
    setEditModal(record)
    editForm.setFieldsValue({ password: '', role: record.role })
  }

  const handleEditSave = async () => {
    try {
      const values = await editForm.validateFields()
      const body: any = { role: values.role }
      if (values.password) body.password = values.password
      await client.put(`/admin/users/${editModal.id}`, body)
      message.success('用户已更新')
      setEditModal(null)
      loadUsers()
    } catch (e: any) {
      if (e.response?.data?.detail) message.error(e.response.data.detail)
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '用户名', dataIndex: 'username', width: 120 },
    {
      title: '角色', dataIndex: 'role', width: 80,
      render: (r: string) => <Tag color={r === 'admin' ? 'red' : 'blue'}>{r === 'admin' ? '管理员' : '用户'}</Tag>
    },
    {
      title: '状态', dataIndex: 'status', width: 80,
      render: (s: string) => <Tag color={s === 'active' ? 'green' : 'default'}>{s === 'active' ? '正常' : '禁用'}</Tag>
    },
    {
      title: 'Cookie', dataIndex: 'has_cookie', width: 80,
      render: (v: boolean) => v ? <Tag color="green">已配置</Tag> : <Tag>未配置</Tag>
    },
    {
      title: '注册时间', dataIndex: 'created_at', width: 160,
      render: (t: string) => t ? new Date(t).toLocaleString('zh-CN') : '-'
    },
    {
      title: '操作', width: 200,
      render: (_: any, record: any) => (
        <Space size="small">
          <Button size="small" onClick={() => handleEdit(record)}>编辑</Button>
          <Popconfirm title={record.status === 'active' ? '确定禁用此用户？' : '确定启用此用户？'}
            onConfirm={() => handleToggleStatus(record)}>
            <Button size="small" danger={record.status === 'active'}>
              {record.status === 'active' ? '禁用' : '启用'}
            </Button>
          </Popconfirm>
          {record.role !== 'admin' && (
            <Popconfirm title="确定删除此用户？" onConfirm={() => handleDelete(record)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </Space>
      )
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Input placeholder="搜索用户名" value={search} onChange={e => setSearch(e.target.value)}
          onPressEnter={handleSearch} style={{ width: 200 }} prefix={<SearchOutlined />} />
        <Button onClick={handleSearch}>搜索</Button>
        <Button icon={<ReloadOutlined />} onClick={() => loadUsers()}>刷新</Button>
      </Space>
      <Table columns={columns} dataSource={users} rowKey="id" loading={loading}
        pagination={{ current: page, total, pageSize: 15, onChange: p => { setPage(p); loadUsers(p) } }} />
      <Modal title="编辑用户" open={!!editModal} onOk={handleEditSave} onCancel={() => setEditModal(null)}>
        <Form form={editForm} layout="vertical">
          <Form.Item label="角色" name="role">
            <Select options={[{ value: 'admin', label: '管理员' }, { value: 'user', label: '用户' }]} />
          </Form.Item>
          <Form.Item label="新密码" name="password" extra="留空则不修改密码">
            <Input.Password placeholder="留空则不修改" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

// ── License Key Management Tab ──────────────────────────────────────────────

function LicenseKeyManagement() {
  const [keys, setKeys] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [genCount, setGenCount] = useState(5)
  const [genLoading, setGenLoading] = useState(false)
  const [newKeys, setNewKeys] = useState<string[]>([])
  const [statusFilter, setStatusFilter] = useState('')

  const loadKeys = useCallback(async (p = page, s = statusFilter) => {
    setLoading(true)
    try {
      const params: any = { page: p, page_size: 15 }
      if (s) params.status = s
      const r = await client.get('/admin/license-keys', { params })
      if (r.data.success) {
        setKeys(r.data.data.items)
        setTotal(r.data.data.total)
      }
    } catch { }
    setLoading(false)
  }, [page, statusFilter])

  useEffect(() => { loadKeys() }, [])

  const handleGenerate = async () => {
    setGenLoading(true)
    try {
      const r = await client.post('/admin/license-keys', { count: genCount })
      if (r.data.success) {
        setNewKeys(r.data.data.keys)
        message.success(r.data.message)
        loadKeys()
      }
    } catch (e: any) {
      message.error(e.response?.data?.detail || '生成失败')
    }
    setGenLoading(false)
  }

  const handleDelete = async (record: any) => {
    try {
      await client.delete(`/admin/license-keys/${record.id}`)
      message.success('卡密已删除')
      loadKeys()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '删除失败')
    }
  }

  const copyAllKeys = () => {
    navigator.clipboard.writeText(newKeys.join('\n'))
    message.success('已复制全部卡密')
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    {
      title: '卡密', dataIndex: 'key', width: 240,
      render: (k: string) => <Text code copyable>{k}</Text>
    },
    {
      title: '状态', dataIndex: 'status', width: 80,
      render: (s: string) => {
        const color = s === 'unused' ? 'green' : s === 'used' ? 'blue' : 'default'
        const label = s === 'unused' ? '未使用' : s === 'used' ? '已使用' : '已禁用'
        return <Tag color={color}>{label}</Tag>
      }
    },
    {
      title: '使用者ID', dataIndex: 'used_by', width: 80,
      render: (v: number) => v || '-'
    },
    {
      title: '使用时间', dataIndex: 'used_at', width: 160,
      render: (t: string) => t ? new Date(t).toLocaleString('zh-CN') : '-'
    },
    {
      title: '操作', width: 80,
      render: (_: any, record: any) => (
        <Popconfirm title="确定删除此卡密？" onConfirm={() => handleDelete(record)}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      )
    },
  ]

  return (
    <div>
      <Card title="生成卡密" style={{ marginBottom: 16 }}>
        <Space>
          <span>数量：</span>
          <InputNumber min={1} max={100} value={genCount} onChange={v => setGenCount(v || 5)} />
          <Button type="primary" icon={<PlusOutlined />} loading={genLoading} onClick={handleGenerate}>
            生成
          </Button>
        </Space>
        {newKeys.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <Space style={{ marginBottom: 8 }}>
              <Tag color="green">已生成 {newKeys.length} 张卡密</Tag>
              <Button size="small" icon={<CopyOutlined />} onClick={copyAllKeys}>复制全部</Button>
            </Space>
            <div style={{ background: '#f6f6f6', padding: 12, borderRadius: 8, maxHeight: 200, overflowY: 'auto', fontFamily: 'monospace', fontSize: 13 }}>
              {newKeys.map((k, i) => <div key={i}>{k}</div>)}
            </div>
          </div>
        )}
      </Card>

      <Space style={{ marginBottom: 16 }}>
        <Select placeholder="状态筛选" allowClear value={statusFilter || undefined} onChange={v => { setStatusFilter(v || ''); setPage(1); loadKeys(1, v || '') }}
          style={{ width: 120 }} options={[
            { value: 'unused', label: '未使用' },
            { value: 'used', label: '已使用' },
            { value: 'disabled', label: '已禁用' },
          ]} />
        <Button icon={<ReloadOutlined />} onClick={() => loadKeys()}>刷新</Button>
      </Space>
      <Table columns={columns} dataSource={keys} rowKey="id" loading={loading}
        pagination={{ current: page, total, pageSize: 15, onChange: p => { setPage(p); loadKeys(p) } }} />
    </div>
  )
}

// ── Announcement Management Tab ─────────────────────────────────────────────

function AnnouncementManagement() {
  const [anns, setAnns] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(false)
  const [editing, setEditing] = useState<any>(null)
  const [form] = Form.useForm()

  const loadAnns = useCallback(async () => {
    setLoading(true)
    try {
      const r = await client.get('/admin/announcements')
      if (r.data.success) setAnns(r.data.data)
    } catch { }
    setLoading(false)
  }, [])

  useEffect(() => { loadAnns() }, [])

  const handleCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ active: true })
    setModal(true)
  }

  const handleEdit = (record: any) => {
    setEditing(record)
    form.setFieldsValue({ title: record.title, content: record.content, active: record.active })
    setModal(true)
  }

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      if (editing) {
        await client.put(`/admin/announcements/${editing.id}`, values)
        message.success('公告已更新')
      } else {
        await client.post('/admin/announcements', values)
        message.success('公告已创建')
      }
      setModal(false)
      loadAnns()
    } catch (e: any) {
      if (e.response?.data?.detail) message.error(e.response.data.detail)
    }
  }

  const handleDelete = async (record: any) => {
    try {
      await client.delete(`/admin/announcements/${record.id}`)
      message.success('公告已删除')
      loadAnns()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '删除失败')
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '标题', dataIndex: 'title', width: 200 },
    { title: '内容', dataIndex: 'content', ellipsis: true },
    {
      title: '状态', dataIndex: 'active', width: 80,
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '激活' : '停用'}</Tag>
    },
    {
      title: '创建时间', dataIndex: 'created_at', width: 160,
      render: (t: string) => t ? new Date(t).toLocaleString('zh-CN') : '-'
    },
    {
      title: '操作', width: 140,
      render: (_: any, record: any) => (
        <Space size="small">
          <Button size="small" onClick={() => handleEdit(record)}>编辑</Button>
          <Popconfirm title="确定删除此公告？" onConfirm={() => handleDelete(record)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      )
    },
  ]

  return (
    <div>
      <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate} style={{ marginBottom: 16 }}>
        新建公告
      </Button>
      <Table columns={columns} dataSource={anns} rowKey="id" loading={loading} pagination={false} />
      <Modal title={editing ? '编辑公告' : '新建公告'} open={modal} onOk={handleSave} onCancel={() => setModal(false)} width={600}>
        <Form form={form} layout="vertical">
          <Form.Item label="标题" name="title" rules={[{ required: true, message: '请输入标题' }]}>
            <Input placeholder="公告标题" />
          </Form.Item>
          <Form.Item label="内容" name="content" rules={[{ required: true, message: '请输入内容' }]}>
            <Input.TextArea rows={4} placeholder="公告内容" />
          </Form.Item>
          <Form.Item label="激活" name="active" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

// ── Model Config Tab ────────────────────────────────────────────────────────

function ModelConfigManagement() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [testLoading, setTestLoading] = useState(false)

  useEffect(() => {
    client.get('/admin/model-config').then(r => {
      if (r.data.success) {
        form.setFieldsValue(r.data.data)
      }
    }).catch(() => {})
  }, [])

  const handleSave = async () => {
    setLoading(true)
    try {
      const values = await form.validateFields()
      await client.put('/admin/model-config', values)
      message.success('模型配置已保存')
    } catch (e: any) {
      message.error(e.response?.data?.detail || '保存失败')
    }
    setLoading(false)
  }

  const handleTest = async () => {
    setTestLoading(true)
    try {
      const r = await client.post('/admin/model-config/test')
      if (r.data.success) {
        message.success(r.data.message)
      } else {
        message.warning(r.data.message)
      }
    } catch (e: any) {
      message.error('测试失败')
    }
    setTestLoading(false)
  }

  return (
    <Card style={{ maxWidth: 600 }}>
      <Form form={form} layout="vertical">
        <Form.Item label="AI 提供商" name="llm_provider">
          <Select options={[
            { value: 'openai', label: 'OpenAI 兼容' },
            { value: 'mimo', label: 'MiMo' },
          ]} />
        </Form.Item>
        <Form.Item label="API Key" name="llm_api_key">
          <Input.Password placeholder="sk-..." />
        </Form.Item>
        <Form.Item label="模型" name="llm_model">
          <Input placeholder="如 gpt-4o, mimo-v2.5" />
        </Form.Item>
        <Form.Item label="Base URL" name="llm_base_url">
          <Input placeholder="https://api.openai.com/v1" />
        </Form.Item>
        <Space>
          <Button type="primary" icon={<SettingOutlined />} loading={loading} onClick={handleSave}>保存配置</Button>
          <Button icon={<RobotOutlined />} loading={testLoading} onClick={handleTest}>测试连接</Button>
        </Space>
      </Form>
    </Card>
  )
}

// ── Admin Main Page ─────────────────────────────────────────────────────────

export default function AdminPage() {
  const [stats, setStats] = useState({ users: 0, keys: 0, keysUsed: 0 })

  useEffect(() => {
    // Load stats
    client.get('/admin/users', { params: { page: 1, page_size: 1 } }).then(r => {
      if (r.data.success) setStats(s => ({ ...s, users: r.data.data.total }))
    }).catch(() => {})
    client.get('/admin/license-keys', { params: { page: 1, page_size: 1 } }).then(r => {
      if (r.data.success) setStats(s => ({ ...s, keys: r.data.data.total }))
    }).catch(() => {})
    client.get('/admin/license-keys', { params: { page: 1, page_size: 1, status: 'used' } }).then(r => {
      if (r.data.success) setStats(s => ({ ...s, keysUsed: r.data.data.total }))
    }).catch(() => {})
  }, [])

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <Title level={3}>🔧 管理后台</Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card><Statistic title="用户数" value={stats.users} prefix={<UserOutlined />} /></Card>
        </Col>
        <Col span={8}>
          <Card><Statistic title="卡密总数" value={stats.keys} prefix={<KeyOutlined />} /></Card>
        </Col>
        <Col span={8}>
          <Card><Statistic title="已使用卡密" value={stats.keysUsed} prefix={<KeyOutlined />} valueStyle={{ color: '#52c41a' }} /></Card>
        </Col>
      </Row>

      <Tabs items={[
        {
          key: 'users',
          label: <span><UserOutlined /> 用户管理</span>,
          children: <UserManagement />,
        },
        {
          key: 'keys',
          label: <span><KeyOutlined /> 卡密管理</span>,
          children: <LicenseKeyManagement />,
        },
        {
          key: 'announcements',
          label: <span><NotificationOutlined /> 公告管理</span>,
          children: <AnnouncementManagement />,
        },
        {
          key: 'model',
          label: <span><RobotOutlined /> 模型配置</span>,
          children: <ModelConfigManagement />,
        },
      ]} />
    </div>
  )
}
