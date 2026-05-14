import React, { useEffect, useState } from 'react'
import { App,  Card, Table, Button, Space, Typography, Tag, Popconfirm, Input, Tabs, Row, Col, Modal, Form } from 'antd'
import { DeleteOutlined, ExportOutlined, EditOutlined, SendOutlined, PlusOutlined, RobotOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import client from '../../api/client'

const { Title, Text } = Typography

type ContentItem = {
  id: number
  title: string
  content?: string
  desc?: string
  author_name?: string
  likes?: number
  library_tags?: string
  status?: string
  images_json?: string
  created_at?: string
}

export default function MyContentPage() {
  // --- Content Library tab ---
  const [notes, setNotes] = useState<ContentItem[]>([])
  const [notesTotal, setNotesTotal] = useState(0)
  const [notesPage, setNotesPage] = useState(1)
  const [notesLoading, setNotesLoading] = useState(false)
  const [tagFilter, setTagFilter] = useState('')

  // --- Drafts tab ---
  const [drafts, setDrafts] = useState<ContentItem[]>([])
  const [draftsTotal, setDraftsTotal] = useState(0)
  const [draftsPage, setDraftsPage] = useState(1)
  const [draftsLoading, setDraftsLoading] = useState(false)
  const [editing, setEditing] = useState<ContentItem | null>(null)
  const [form] = Form.useForm()
  const [rewriteLoading, setRewriteLoading] = useState(false)

  const [activeTab, setActiveTab] = useState('library')

  const navigate = useNavigate()

  const loadNotes = async () => {
    setNotesLoading(true)
    try {
      const r = await client.get('/content', { params: { page: notesPage, tag: tagFilter } })
      setNotes(r.data.data || [])
      setNotesTotal(r.data.total || 0)
    } catch {}
    setNotesLoading(false)
  }

  const loadDrafts = async () => {
    setDraftsLoading(true)
    try {
      const r = await client.get('/drafts', { params: { page: draftsPage } })
      setDrafts(r.data.data || [])
      setDraftsTotal(r.data.total || 0)
    } catch {}
    setDraftsLoading(false)
  }

  useEffect(() => { if (activeTab === 'library') loadNotes() }, [notesPage, tagFilter, activeTab])
  useEffect(() => { if (activeTab === 'drafts') loadDrafts() }, [draftsPage, activeTab])

  const onDeleteNote = async (id: number) => {
    await client.delete(`/content/${id}`)
    message.success('已移除')
    loadNotes()
  }

  const onExport = async () => {
    const r = await client.post('/content/export', {})
    const blob = new Blob([JSON.stringify(r.data.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'content_library.json'; a.click()
    message.success('导出成功')
  }

  const onDeleteDraft = async (id: number) => {
    await client.delete(`/drafts/${id}`)
    message.success('已删除')
    loadDrafts()
  }

  const onUpdateDraft = async () => {
    if (!editing) return
    const values = form.getFieldsValue()
    await client.put(`/drafts/${editing.id}`, values)
    message.success('已更新')
    setEditing(null)
    loadDrafts()
  }

  const onAIRewrite = async (draft: ContentItem) => {
    setRewriteLoading(true)
    try {
      const r = await client.post('/note/rewrite', {
        title: draft.title, desc: draft.content, style: '小红书爆款', rewrite_ratio: 60,
      })
      if (r.data.success) {
        form.setFieldsValue({ title: r.data.data.title, content: r.data.data.desc })
        message.success('AI改写完成')
      } else {
        message.error(r.data.message)
      }
    } catch {
      message.error('改写失败')
    }
    setRewriteLoading(false)
  }

  const onPublishDraft = async (draft: ContentItem) => {
    try {
      await client.post('/publish', {
        title: draft.title, content: draft.content,
        images_json: draft.images_json,
      })
      message.success('已提交发布')
    } catch {
      message.error('发布失败')
    }
  }

  const onConvertToDraft = async (note: ContentItem) => {
    try {
      await client.post('/drafts', { title: note.title, content: note.desc || note.content || '', images_json: note.images_json || '[]' })
      message.success('已转为草稿')
      loadDrafts()
    } catch {
      message.error('转换失败')
    }
  }

  const libraryColumns = [
    { title: '标题', dataIndex: 'title', ellipsis: true },
    { title: '作者', dataIndex: 'author_name', width: 120 },
    { title: '点赞', dataIndex: 'likes', width: 80 },
    { title: '标签', dataIndex: 'library_tags', render: (v: string) =>
      v ? v.split(',').map((t, i) => <Tag key={i}>{t}</Tag>) : '-' },
    { title: '操作', width: 180, render: (_: any, r: ContentItem) => (
      <Space>
        <Button size="small" icon={<EditOutlined />}
          onClick={() => onConvertToDraft(r)}>
          转草稿
        </Button>
        <Popconfirm title="确定移除？" onConfirm={() => onDeleteNote(r.id)}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>
    )},
  ]

  const draftsColumns = [
    { title: '标题', dataIndex: 'title', ellipsis: true },
    { title: '状态', dataIndex: 'status', width: 100, render: (v: string) => {
      const map: Record<string, { color: string; text: string }> = {
        draft: { color: 'default', text: '草稿' },
        pending: { color: 'orange', text: '待发布' },
        published: { color: 'green', text: '已发布' },
      }
      const s = map[v] || { color: 'default', text: v || '草稿' }
      return <Tag color={s.color}>{s.text}</Tag>
    }},
    { title: '创建时间', dataIndex: 'created_at', width: 160, render: (v: string) => v || '-' },
    { title: '操作', width: 280, render: (_: any, r: ContentItem) => (
      <Space>
        <Button size="small" icon={<EditOutlined />} onClick={() => {
          setEditing(r)
          form.setFieldsValue({ title: r.title, content: r.content })
        }}>
          编辑
        </Button>
        <Button size="small" icon={<RobotOutlined />} loading={rewriteLoading}
          onClick={() => onAIRewrite(r)}>
          AI改写
        </Button>
        <Button size="small" type="primary" icon={<SendOutlined />}
          onClick={() => onPublishDraft(r)}>
          发布
        </Button>
        <Popconfirm title="确定删除？" onConfirm={() => onDeleteDraft(r.id)}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>
    )},
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>我的内容</Title>
        <Space>
          {activeTab === 'library' && (
            <Button icon={<ExportOutlined />} onClick={onExport}>导出JSON</Button>
          )}
          {activeTab === 'drafts' && (
            <Button icon={<ExportOutlined />} onClick={onExport}>导出JSON</Button>
          )}
        </Space>
      </div>

      <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
        {
          key: 'library',
          label: `📚 素材库 (${notesTotal})`,
          children: (
            <>
              <div style={{ marginBottom: 12 }}>
                <Input.Search placeholder="按标签筛选" style={{ width: 200 }}
                  onSearch={v => setTagFilter(v)} allowClear />
              </div>
              <Table dataSource={notes} rowKey="id" loading={notesLoading}
                pagination={{ total: notesTotal, current: notesPage, onChange: setNotesPage, pageSize: 10 }}
                columns={libraryColumns} size="small" />
            </>
          ),
        },
        {
          key: 'drafts',
          label: `✏️ 草稿箱 (${draftsTotal})`,
          children: (
            <Table dataSource={drafts} rowKey="id" loading={draftsLoading}
              pagination={{ total: draftsTotal, current: draftsPage, onChange: setDraftsPage, pageSize: 10 }}
              columns={draftsColumns} size="small" />
          ),
        },
      ]} />

      {/* Edit Draft Modal */}
      <Modal
        title="编辑草稿"
        open={!!editing}
        onCancel={() => setEditing(null)}
        onOk={onUpdateDraft}
        width={700}
        okText="保存"
      >
        <Form form={form} layout="vertical">
          <Form.Item label="标题" name="title">
            <Input />
          </Form.Item>
          <Form.Item label="正文" name="content">
            <Input.TextArea rows={10} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
