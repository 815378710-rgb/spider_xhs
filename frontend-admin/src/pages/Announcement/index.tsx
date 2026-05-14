import React, { useState, useEffect, useCallback } from 'react'
import {
  App, Card, Table, Button, Space, Typography, Tag, Modal, Form,
  Input, Switch, Popconfirm, Descriptions
} from 'antd'
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined,
  NotificationOutlined as MegaphoneOutlined
} from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text } = Typography
const { TextArea } = Input

interface Announcement {
  id: number
  title: string
  content: string
  active: boolean
  created_at: string
}

export default function AnnouncementPage() {
  const { message } = App.useApp()
  const [list, setList] = useState<Announcement[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Announcement | null>(null)
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const r = await client.get('/admin/announcements')
      if (r.data.success) {
        setList(r.data.data || [])
      }
    } catch {
      message.error('获取公告列表失败')
    }
    setLoading(false)
  }, [])

  useEffect(() => { fetchList() }, [fetchList])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ active: true })
    setModalOpen(true)
  }

  const openEdit = (ann: Announcement) => {
    setEditing(ann)
    form.setFieldsValue({
      title: ann.title,
      content: ann.content,
      active: ann.active,
    })
    setModalOpen(true)
  }

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      if (editing) {
        const r = await client.put(`/admin/announcements/${editing.id}`, values)
        if (r.data.success) {
          message.success('公告已更新')
          setModalOpen(false)
          fetchList()
        }
      } else {
        const r = await client.post('/admin/announcements', values)
        if (r.data.success) {
          message.success('公告已创建')
          setModalOpen(false)
          fetchList()
        }
      }
    } catch (e: any) {
      if (e.errorFields) return // form validation
      message.error(e.response?.data?.detail || '操作失败')
    }
    setSaving(false)
  }

  const handleDelete = async (id: number) => {
    try {
      const r = await client.delete(`/admin/announcements/${id}`)
      if (r.data.success) {
        message.success('公告已删除')
        fetchList()
      }
    } catch {
      message.error('删除失败')
    }
  }

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      ellipsis: true,
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: '内容',
      dataIndex: 'content',
      ellipsis: true,
      render: (v: string) => <Text type="secondary">{v}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'active',
      width: 80,
      render: (v: boolean) => (
        v ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 180,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      width: 140,
      render: (_: any, record: Announcement) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除此公告？" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Space>
          <MegaphoneOutlined style={{ fontSize: 20 }} />
          <Title level={4} style={{ margin: 0 }}>公告管理</Title>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchList}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            发布公告
          </Button>
        </Space>
      </div>

      <Card>
        <Table
          dataSource={list}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{ emptyText: '暂无公告' }}
        />
      </Card>

      <Modal
        title={editing ? '编辑公告' : '发布公告'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        confirmLoading={saving}
        okText={editing ? '保存' : '发布'}
        width={600}
      >
        <Form form={form} layout="vertical" initialValues={{ active: true }}>
          <Form.Item name="title" label="公告标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input placeholder="输入公告标题" maxLength={100} />
          </Form.Item>
          <Form.Item name="content" label="公告内容" rules={[{ required: true, message: '请输入内容' }]}>
            <TextArea rows={6} placeholder="输入公告内容，支持多行文本" />
          </Form.Item>
          <Form.Item name="active" label="是否启用" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
