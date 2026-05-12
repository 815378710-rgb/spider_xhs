import React, { useState } from 'react'
import { Card, Input, Select, Button, Table, Space, Typography, Row, Col, message, Tag, Modal, Image, Spin, Empty } from 'antd'
import { SearchOutlined, SaveOutlined, EyeOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text, Paragraph } = Typography

export default function DiscoveryPage() {
  const [query, setQuery] = useState('')
  const [sortType, setSortType] = useState(0)
  const [noteType, setNoteType] = useState(0)
  const [results, setResults] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  // ── 笔记详情弹窗 ──────────────────────────────────────────────
  const [detailVisible, setDetailVisible] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailNote, setDetailNote] = useState<any>(null)
  const [detailImages, setDetailImages] = useState<string[]>([])

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
    try {
      await client.post('/content/save', { note_id: noteId })
      message.success('已保存到素材库')
    } catch (e: any) {
      message.error('保存失败: ' + (e.response?.data?.message || e.message))
    }
  }

  const onViewNote = async (noteId: string) => {
    setDetailVisible(true)
    setDetailLoading(true)
    setDetailNote(null)
    setDetailImages([])
    try {
      const r = await client.post('/note/detail', { note_id: noteId })
      if (r.data.success) {
        const data = r.data.data
        setDetailNote({
          title: data.title || '',
          desc: data.desc || '',
          author: data.user?.nickname || '',
          likes: data.interact_info?.liked_count || 0,
          collects: data.interact_info?.collected_count || 0,
          comments: data.interact_info?.comment_count || 0,
          type: data.type || '',
          tags: (data.tag_list || []).map((t: any) => t.name).filter(Boolean),
        })
        // Extract image URLs
        const imgs: string[] = []
        for (const img of (data.image_list || [])) {
          const infoList = img.info_list || []
          let url = ''
          if (infoList.length > 1) url = infoList[1].url || ''
          else if (infoList.length > 0) url = infoList[0].url || ''
          if (!url) url = img.url_default || img.url_pre || ''
          if (url) imgs.push(url)
        }
        setDetailImages(imgs)
      } else {
        message.warning(r.data.message || '获取笔记详情失败')
        setDetailVisible(false)
      }
    } catch (e: any) {
      message.error('获取详情失败: ' + (e.response?.data?.message || e.message))
      setDetailVisible(false)
    }
    setDetailLoading(false)
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
            { title: '操作', width: 150, render: (_: any, r: any) => (
              <Space>
                <Button size="small" icon={<SaveOutlined />} onClick={() => onSaveToLibrary(r.note_id)}>
                  入库
                </Button>
                <Button size="small" type="link" icon={<EyeOutlined />} onClick={() => onViewNote(r.note_id)}>
                  查看
                </Button>
              </Space>
            )},
          ]} />
      </Card>

      {/* 笔记详情弹窗 */}
      <Modal
        title="📝 笔记详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailVisible(false)}>关闭</Button>,
          detailNote && <Button key="save" type="primary" icon={<SaveOutlined />}
            onClick={() => onSaveToLibrary(detailNote.note_id || results.find(r => r.title === detailNote.title)?.note_id || '')}>
            入库
          </Button>,
        ]}
        width={700}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin tip="加载笔记详情中..." /></div>
        ) : detailNote ? (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Title level={4}>{detailNote.title}</Title>
            <Text type="secondary">作者: {detailNote.author} | 👍 {detailNote.likes} | ⭐ {detailNote.collects} | 💬 {detailNote.comments}</Text>
            {detailNote.tags.length > 0 && (
              <Space wrap>
                {detailNote.tags.map((t: string, i: number) => <Tag key={i}>#{t}</Tag>)}
              </Space>
            )}
            <Paragraph style={{ whiteSpace: 'pre-wrap' }}>{detailNote.desc}</Paragraph>
            {detailImages.length > 0 && (
              <div>
                <Text strong>图片:</Text>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                  {detailImages.map((url, i) => (
                    <Image key={i} src={url} width={150} height={150} style={{ objectFit: 'cover', borderRadius: 8 }}
                      fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg==" />
                  ))}
                </div>
              </div>
            )}
          </Space>
        ) : (
          <Empty description="无数据" />
        )}
      </Modal>
    </div>
  )
}
