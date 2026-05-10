import React, { useState } from 'react'
import { Card, Input, Select, Button, Table, Space, Typography, Row, Col, message, Tag } from 'antd'
import { SearchOutlined, SaveOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text } = Typography

export default function DiscoveryPage() {
  const [query, setQuery] = useState('')
  const [sortType, setSortType] = useState(0)
  const [noteType, setNoteType] = useState(0)
  const [results, setResults] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const onSearch = async () => {
    if (!query.trim()) return message.warning('请输入搜索关键词')
    setLoading(true)
    try {
      const r = await client.post('/search/notes', { query, sort_type: sortType, note_type: noteType })
      setResults(r.data.data || [])
    } catch (e: any) {
      message.error(e.response?.data?.detail || '搜索失败')
    }
    setLoading(false)
  }

  const onSaveToLibrary = async (noteId: string) => {
    await client.post('/content/save', { note_id: noteId })
    message.success('已保存到素材库')
  }

  return (
    <div>
      <Title level={4}>🔍 热门发现</Title>
      <Text type="secondary">搜索小红书热门笔记，一键入库</Text>
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col flex="auto">
            <Input.Search size="large" placeholder="搜索小红书笔记..."
              value={query} onChange={e => setQuery(e.target.value)}
              onSearch={onSearch} enterButton={<><SearchOutlined /> 搜索</>} />
          </Col>
          <Col>
            <Select value={sortType} onChange={setSortType} style={{ width: 120 }}
              options={[
                { value: 0, label: '综合排序' }, { value: 1, label: '最新' },
                { value: 2, label: '最热' }, { value: 3, label: '最多评论' },
              ]} />
          </Col>
          <Col>
            <Select value={noteType} onChange={setNoteType} style={{ width: 100 }}
              options={[
                { value: 0, label: '全部' }, { value: 1, label: '视频' }, { value: 2, label: '图文' },
              ]} />
          </Col>
        </Row>
      </Card>
      <Card>
        <Table dataSource={results} rowKey="note_id" loading={loading} pagination={{ pageSize: 20 }}
          columns={[
            { title: '标题', dataIndex: 'title', ellipsis: true, width: 300 },
            { title: '作者', dataIndex: 'author', width: 120 },
            { title: '类型', dataIndex: 'note_type', width: 80, render: (v: string) =>
              <Tag color={v === 'video' ? 'red' : 'blue'}>{v === 'video' ? '视频' : '图文'}</Tag> },
            { title: '点赞', dataIndex: 'likes', width: 80 },
            { title: '操作', width: 120, render: (_: any, r: any) => (
              <Space>
                <Button size="small" icon={<SaveOutlined />} onClick={() => onSaveToLibrary(r.note_id)}>
                  入库
                </Button>
                <Button size="small" type="link" href={r.url} target="_blank">查看</Button>
              </Space>
            )},
          ]} />
      </Card>
    </div>
  )
}
