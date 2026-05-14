import React, { useState } from 'react'
import { App,  Card, Table, Button, Space, Typography, Input, Drawer, Descriptions } from 'antd'
import { SearchOutlined, UserOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title } = Typography

export default function KOLPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [profile, setProfile] = useState<any>(null)

  const onSearch = async () => {
    if (!query.trim()) return message.warning('请输入搜索关键词')
    setLoading(true)
    try {
      const r = await client.post('/kol/search', { page: 1, category: query })
      setResults(r.data.data || [])
    } catch (e: any) {
      message.error('搜索失败')
    }
    setLoading(false)
  }

  const onViewProfile = async (userId: string) => {
    try {
      const r = await client.get(`/kol/${userId}/profile`)
      setProfile(r.data.data || {})
    } catch {}
  }

  return (
    <div>
      <Title level={4}>蒲公英 KOL 搜索</Title>
      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Input.Search size="large" placeholder="搜索KOL..."
            value={query} onChange={e => setQuery(e.target.value)}
            onSearch={onSearch} enterButton={<><SearchOutlined /> 搜索</>} />
        </Space>
      </Card>
      <Card>
        <Table dataSource={results} rowKey="user_id" loading={loading} pagination={false}
          columns={[
            { title: '昵称', dataIndex: 'nickname', width: 150 },
            { title: 'ID', dataIndex: 'user_id', width: 120 },
            { title: '粉丝', dataIndex: 'fans', width: 100 },
            { title: '操作', width: 100, render: (_: any, r: any) => (
              <Button size="small" icon={<UserOutlined />} onClick={() => onViewProfile(r.user_id)}>详情</Button>
            )},
          ]} />
      </Card>
      <Drawer title="KOL 详情" open={!!profile} onClose={() => setProfile(null)} width={500}>
        {profile && (
          <Descriptions column={1} bordered size="small">
            {Object.entries(profile).map(([k, v]) => (
              <Descriptions.Item key={k} label={k}>{String(v)}</Descriptions.Item>
            ))}
          </Descriptions>
        )}
      </Drawer>
    </div>
  )
}
