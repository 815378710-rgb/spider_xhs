import React, { useState } from 'react'
import { Card, Input, Button, Typography, Space, Slider, Switch, Select, Tag, Collapse, Divider, message, Progress, Image, Spin, Tabs } from 'antd'
import { LinkOutlined, ThunderboltOutlined, EditOutlined, PictureOutlined, RocketOutlined, CopyOutlined, CheckOutlined, SendOutlined, SaveOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

interface QuickWorkResult {
  original: {
    note_id: string
    title: string
    desc: string
    author: string
    likes: number | string
    collects: number | string
    comments: number | string
  }
  rewritten: {
    title: string
    desc: string
    agent_name?: string
    agent_emoji?: string
  }
  debate?: {
    winner: any
    scores: Record<string, number>
    reasoning: string
    all_versions: any[]
  }
  images_original: string[]
  images_processed: { original: string; processed: string | null; error?: string }[]
}

const REWRITE_STYLES = [
  "保持原风格", "小红书爆款", "种草安利", "教程攻略",
  "测评对比", "日常分享", "探店打卡", "好物推荐",
  "干货知识", "故事叙述", "情感表达", "专业分析",
]

export default function QuickWorkPage() {
  const [url, setUrl] = useState('')
  const [style, setStyle] = useState('保持原风格')
  const [ratio, setRatio] = useState(50)
  const [debate, setDebate] = useState(true)
  const [imageLevel, setImageLevel] = useState('medium')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<QuickWorkResult | null>(null)
  const [progress, setProgress] = useState('')
  const [copied, setCopied] = useState<'title' | 'desc' | null>(null)

  const handleRun = async () => {
    if (!url.trim()) {
      message.warning('请输入笔记链接')
      return
    }
    setLoading(true)
    setResult(null)
    setProgress('正在采集笔记...')

    try {
      const resp = await client.post('/quick-work/run', {
        url: url.trim(),
        style,
        ratio,
        debate,
        image_level: imageLevel,
      })
      if (resp.data.success) {
        setResult(resp.data.data)
        message.success(resp.data.message)
      } else {
        message.error(resp.data.message)
      }
    } catch (e: any) {
      message.error(e.response?.data?.message || e.message || '请求失败')
    } finally {
      setLoading(false)
      setProgress('')
    }
  }

  const copyText = (text: string, type: 'title' | 'desc') => {
    navigator.clipboard.writeText(text)
    setCopied(type)
    message.success('已复制')
    setTimeout(() => setCopied(null), 2000)
  }

  const rewrittenTitle = result?.rewritten?.title || ''
  const rewrittenDesc = result?.rewritten?.desc || ''

  const [saving, setSaving] = useState(false)
  const [publishing, setPublishing] = useState(false)

  const handleSaveDraft = async () => {
    if (!result) return
    setSaving(true)
    try {
      await client.post('/drafts', {
        title: rewrittenTitle,
        content: rewrittenDesc,
        images_json: JSON.stringify(result.images_original || []),
        source_note_id: result.original?.note_id,
      })
      message.success('已存入草稿箱')
    } catch {
      message.error('保存失败')
    }
    setSaving(false)
  }

  const handlePublish = async () => {
    if (!result) return
    setPublishing(true)
    try {
      await client.post('/publish', {
        title: rewrittenTitle,
        content: rewrittenDesc,
        images_json: JSON.stringify(result.images_processed?.filter(i => i.processed).map(i => i.processed) || []),
      })
      message.success('已提交发布！可到发布中心查看状态')
    } catch {
      message.error('发布失败')
    }
    setPublishing(false)
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <Title level={3}>⚡ 一站式工作台</Title>
      <Text type="secondary">粘贴笔记链接 → 采集 → AI改写 → 图片降重 → 一键发布，全程自动化</Text>

      <Card style={{ marginTop: 24, marginBottom: 24 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text strong>📎 笔记链接</Text>
            <TextArea
              rows={2}
              placeholder="粘贴小红书笔记链接（支持正常链接和 xhslink.com 短链接）"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              style={{ marginTop: 8 }}
            />
          </div>

          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <Text strong>🎨 改写风格</Text>
              <Select
                options={REWRITE_STYLES.map(s => ({ label: s, value: s }))}
                value={style}
                onChange={setStyle}
                style={{ width: '100%', marginTop: 8 }}
              />
            </div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <Text strong>📊 改写比例: {ratio}%</Text>
              <Slider min={20} max={90} value={ratio} onChange={setRatio} style={{ marginTop: 8 }} />
            </div>
            <div style={{ minWidth: 200 }}>
              <Text strong>🤖 Agent辩论</Text>
              <div style={{ marginTop: 12 }}>
                <Switch checked={debate} onChange={setDebate} checkedChildren="开" unCheckedChildren="关" />
                <Text type="secondary" style={{ marginLeft: 8 }}>{debate ? '3个Agent竞争选出最优' : '单次改写'}</Text>
              </div>
            </div>
            <div style={{ minWidth: 200 }}>
              <Text strong>🖼️ 图片降重</Text>
              <Select
                options={[
                  { label: '轻度', value: 'light' },
                  { label: '中度', value: 'medium' },
                  { label: '重度', value: 'heavy' },
                ]}
                value={imageLevel}
                onChange={setImageLevel}
                style={{ width: '100%', marginTop: 8 }}
              />
            </div>
          </div>

          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            size="large"
            loading={loading}
            onClick={handleRun}
            style={{ width: 200, height: 48 }}
          >
            {loading ? progress || '处理中...' : '一键开始'}
          </Button>
        </Space>
      </Card>

      {loading && progress && (
        <Card style={{ marginBottom: 24 }}>
          <Spin size="small" /> <Text>{progress}</Text>
          <Progress percent={30} status="active" style={{ marginTop: 12 }} />
        </Card>
      )}

      {result && (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {/* 原始笔记 */}
          {result.original && (
            <Card title="📝 原始笔记" extra={
              <Space>
                <Tag color="blue">👍 {result.original.likes}</Tag>
                <Tag color="green">⭐ {result.original.collects}</Tag>
                <Tag color="orange">💬 {result.original.comments}</Tag>
              </Space>
            }>
              <Title level={4}>{result.original.title}</Title>
              <Paragraph>{result.original.desc}</Paragraph>
              <Text type="secondary">作者: {result.original.author}</Text>
            </Card>
          )}

          {/* AI改写结果 */}
          {result.rewritten && (
            <Card
              title={`✨ AI改写 ${result.rewritten.agent_name ? `(${result.rewritten.agent_emoji} ${result.rewritten.agent_name})` : ''}`}
              style={{ border: '2px solid #ff4757' }}
              extra={
                <Tag color="red">改写完成</Tag>
              }
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>
                  <Text strong>标题：</Text>
                  <div style={{ background: '#f6f6f6', padding: 12, borderRadius: 8, marginTop: 4 }}>
                    {rewrittenTitle}
                    <Button
                      size="small"
                      type="link"
                      icon={copied === 'title' ? <CheckOutlined /> : <CopyOutlined />}
                      onClick={() => copyText(rewrittenTitle, 'title')}
                    />
                  </div>
                </div>
                <div>
                  <Text strong>正文：</Text>
                  <div style={{ background: '#f6f6f6', padding: 12, borderRadius: 8, marginTop: 4, whiteSpace: 'pre-wrap' }}>
                    {rewrittenDesc}
                    <Button
                      size="small"
                      type="link"
                      icon={copied === 'desc' ? <CheckOutlined /> : <CopyOutlined />}
                      onClick={() => copyText(rewrittenDesc, 'desc')}
                    />
                  </div>
                </div>
              </Space>

              {/* 辩论结果 */}
              {result.debate && (
                <Collapse style={{ marginTop: 16 }} items={[
                  {
                    key: 'debate',
                    label: `🏆 辩论评审 (评分: ${Object.entries(result.debate.scores || {}).map(([k, v]) => `${k}:${v}`).join(', ')})`,
                    children: (
                      <div>
                        <Paragraph>{result.debate.reasoning}</Paragraph>
                        {result.debate.all_versions?.map((v, i) => (
                          <Card key={i} size="small" style={{ marginBottom: 8 }}
                            title={`${v.agent_emoji || ''} ${v.agent_name || `方案${i + 1}`}`}
                            extra={v.agent === result.debate?.winner?.agent ? <Tag color="red">最优</Tag> : null}
                          >
                            <Text strong>{v.title}</Text>
                            <Paragraph type="secondary" ellipsis={{ rows: 2 }}>{v.desc}</Paragraph>
                          </Card>
                        ))}
                      </div>
                    ),
                  },
                ]} />
              )}
            </Card>
          )}

          {/* 图片处理 */}
          {result.images_processed.length > 0 && (
            <Card title={`🖼️ 图片降重 (${result.images_processed.filter(i => i.processed).length}/${result.images_processed.length})`}>
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {result.images_processed.map((img, i) => (
                  <div key={i} style={{ textAlign: 'center' }}>
                    <div style={{ display: 'flex', gap: 8 }}>
                      {img.original && (
                        <div>
                          <Text type="secondary" style={{ fontSize: 12 }}>原图</Text>
                          <Image
                            src={img.original.startsWith('http') ? img.original : `/api/images/proxy?url=${encodeURIComponent(img.original)}`}
                            width={120} height={120} style={{ objectFit: 'cover', borderRadius: 8 }}
                            fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
                          />
                        </div>
                      )}
                      {img.processed && (
                        <div>
                          <Text type="secondary" style={{ fontSize: 12 }}>降重后</Text>
                          <Image
                            src={img.processed}
                            width={120} height={120} style={{ objectFit: 'cover', borderRadius: 8 }}
                            fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
                          />
                        </div>
                      )}
                    </div>
                    {img.error && <Text type="danger" style={{ fontSize: 11 }}>{img.error}</Text>}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* 原图预览 */}
          {!result.images_processed.length && result.images_original.length > 0 && (
            <Card title={`🖼️ 原图 (${result.images_original.length}张)`}>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {result.images_original.map((img, i) => (
                  <Image
                    key={i}
                    src={img.startsWith('http') ? img : `/api/images/proxy?url=${encodeURIComponent(img)}`}
                    width={150} height={150} style={{ objectFit: 'cover', borderRadius: 8 }}
                    fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
                  />
                ))}
              </div>
            </Card>
          )}

          {/* 底部操作栏 - 流程闭环 */}
          <Card style={{ background: 'linear-gradient(135deg, #f6ffed 0%, #fff 100%)', border: '1px solid #b7eb8f' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <Text strong style={{ fontSize: 16 }}>✅ 内容已就绪</Text>
                <br />
                <Text type="secondary">你可以直接发布，或者存入草稿箱稍后编辑</Text>
              </div>
              <Space size="middle">
                <Button size="large" icon={<SaveOutlined />} loading={saving} onClick={handleSaveDraft}>
                  存入草稿
                </Button>
                <Button type="primary" size="large" icon={<SendOutlined />} loading={publishing} onClick={handlePublish}
                  style={{ background: '#ff4757', borderColor: '#ff4757' }}>
                  一键发布
                </Button>
              </Space>
            </div>
          </Card>
        </Space>
      )}
    </div>
  )
}
