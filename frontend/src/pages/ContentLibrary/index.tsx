import React, { useEffect, useState } from 'react'
import { App,  Card, Table, Button, Space, Typography, Tag, Popconfirm, Input, Select, Row, Col } from 'antd'
import { DeleteOutlined, ExportOutlined, EditOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import client from '../../api/client'

const { Title } = Typography

export default function ContentLibraryPage() {
  const [notes, setNotes] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [tagFilter, setTagFilter] = useState('')
  const navigate = useNavigate()

  const load = async () => {
    setLoading(true)
    try {
      const r = await client.get('/content', { params: { page, tag: tagFilter } })
      setNotes(r.data.data || [])
      setTotal(r.data.total || 0)
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [page, tagFilter])

  const onDelete = async (id: number) => {
    await client.delete(`/content/${id}`)
    message.success('已移除')
    load()
  }

  const onExport = async () => {
    const r = await client.post('/content/export', {})
    const blob = new Blob([JSON.stringify(r.data.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'content_library.json'; a.click()
    message.success('导出成功')
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>内容素材库</Title>
        <Space>
          <Input.Search placeholder="按标签筛选" style={{ width: 200 }}
            onSearch={v => setTagFilter(v)} allowClear />
          <Button icon={<ExportOutlined />} onClick={onExport}>导出JSON</Button>
        </Space>
      </div>
      <Card>
        <Table dataSource={notes} rowKey="id" loading={loading} pagination={{ total, current: page, onChange: setPage }}
          columns={[
            { title: '标题', dataIndex: 'title', ellipsis: true },
            { title: '作者', dataIndex: 'author_name', width: 120 },
            { title: '点赞', dataIndex: 'likes', width: 80 },
            { title: '标签', dataIndex: 'library_tags', render: (v: string) =>
              v ? v.split(',').map((t, i) => <Tag key={i}>{t}</Tag>) : '-' },
            { title: '操作', width: 150, render: (_: any, r: any) => (
              <Space>
                <Button size="small" icon={<EditOutlined />}
                  onClick={() => { localStorage.setItem('edit_note', JSON.stringify(r)); navigate('/drafts') }}>
                  编辑
                </Button>
                <Popconfirm title="确定移除？" onConfirm={() => onDelete(r.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            )},
          ]} />
      </Card>
    </div>
  )
}
