import React, { useState } from 'react'
import { Card, Input, Button, Row, Col, Typography, Tag, Space, Spin, Empty, message } from 'antd'
import { BulbOutlined, HeartOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text, Paragraph } = Typography

export default function TopicRecommendPage() {
  const [keyword, setKeyword] = useState('')
  const [topics, setTopics] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const onRecommend = async () => {
    if (!keyword.trim()) return message.warning('请输入关键词或领域')
    setLoading(true)
    try {
      const r = await client.post('/topics/recommend', { keyword, count: 6 })
      if (r.data.success) {
        setTopics(r.data.data || [])
        message.success(`已推荐 ${r.data.data?.length || 0} 个选题`)
      } else {
        message.error(r.data.message || '推荐失败')
      }
    } catch (e: any) {
      message.error(e.response?.data?.detail || '推荐失败')
    }
    setLoading(false)
  }

  const heatColor: Record<string, string> = { '高': 'red', '中': 'orange', '低': 'default' }

  return (
    <div>
      <Title level={4}>
        <BulbOutlined style={{ color: '#faad14' }} /> 爆款选题推荐
      </Title>
      <Text type="secondary">输入关键词或领域，AI 帮你分析热门趋势并推荐爆款选题</Text>

      <Card style={{ marginTop: 16, marginBottom: 24 }}>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            size="large"
            placeholder="输入关键词，如：护肤、健身、穿搭、美食..."
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            onPressEnter={onRecommend}
          />
          <Button type="primary" size="large" loading={loading} onClick={onRecommend}>
            <BulbOutlined /> 获取推荐
          </Button>
        </Space.Compact>
      </Card>

      <Spin spinning={loading}>
        {topics.length > 0 ? (
          <Row gutter={[16, 16]}>
            {topics.map((t: any, i: number) => (
              <Col span={12} key={i}>
                <Card hoverable style={{ height: '100%' }}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <Title level={5} style={{ margin: 0, flex: 1 }}>{t.title}</Title>
                      <Tag color={heatColor[t.heat] || 'default'} style={{ marginLeft: 8, flexShrink: 0 }}>
                        热度: {t.heat}
                      </Tag>
                    </div>
                    <Paragraph type="secondary" style={{ margin: 0 }}>{t.reason}</Paragraph>
                    <Space>
                      <Tag color={t.note_type === '视频' ? 'red' : 'blue'}>{t.note_type}</Tag>
                      {t.tags?.map((tag: string, j: number) => (
                        <Tag key={j}>#{tag}</Tag>
                      ))}
                    </Space>
                    <Button icon={<HeartOutlined />} block>一键入库</Button>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        ) : (
          !loading && <Empty description="输入关键词，获取 AI 选题推荐" />
        )}
      </Spin>
    </div>
  )
}
