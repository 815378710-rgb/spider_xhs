import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Card, Input, Button, Typography, Space, Slider, Switch, Select, Tag, Collapse, Divider, message, Progress, Image, Spin, Tabs, List, Statistic, Row, Col, Tooltip, Empty } from 'antd'
import { LinkOutlined, ThunderboltOutlined, EditOutlined, PictureOutlined, RocketOutlined, CopyOutlined, CheckOutlined, SendOutlined, SaveOutlined, SafetyCertificateOutlined, RobotOutlined, WarningOutlined, ExclamationCircleOutlined, CheckCircleOutlined, StarOutlined, StarFilled, DownloadOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

const STORAGE_KEY = 'xhs_quickwork_result'

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
    scores: Record<string, any>
    reasoning: string
    all_versions: any[]
  }
  images_original: string[]
  images_processed: { original: string; processed: string | null; error?: string }[]
}

const INDUSTRIES = [
  "美妆护肤", "穿搭时尚", "美食料理", "旅行出游",
  "健身减脂", "母婴育儿", "数码科技", "家居生活",
]

const REWRITE_STYLES = [
  "保持原风格", "小红书爆款", "种草安利", "教程攻略",
  "测评对比", "日常分享", "探店打卡", "好物推荐",
  "干货知识", "故事叙述", "情感表达", "专业分析",
]

/** Safely extract total score from scores value (may be number or object with .total) */
function getScoreTotal(scoreValue: any): number {
  if (scoreValue == null) return 0
  if (typeof scoreValue === 'number') return scoreValue
  if (typeof scoreValue === 'object' && scoreValue.total != null) return Number(scoreValue.total) || 0
  return 0
}

/** Render score breakdown if available */
function ScoreBreakdown({ scoreValue }: { scoreValue: any }) {
  if (!scoreValue || typeof scoreValue !== 'object') return null
  const labels: Record<string, string> = {
    title: '标题', content: '内容', interaction: '互动',
    keywords: '关键词', style: '风格', total: '总分'
  }
  const items = Object.entries(scoreValue).filter(([k]) => k !== 'total')
  if (items.length === 0) return null
  return (
    <div style={{ marginTop: 6 }}>
      {items.map(([k, v]) => (
        <Tag key={k} style={{ margin: 2 }}>
          {labels[k] || k}: {String(v)}
        </Tag>
      ))}
    </div>
  )
}

function loadResult(): QuickWorkResult | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch {}
  return null
}

function saveResult(result: QuickWorkResult | null) {
  try {
    if (result) localStorage.setItem(STORAGE_KEY, JSON.stringify(result))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {}
}

export default function QuickWorkPage() {
  const [url, setUrl] = useState('')
  const [style, setStyle] = useState('保持原风格')
  const [ratio, setRatio] = useState(50)
  const [debate, setDebate] = useState(true)
  const [imageLevel, setImageLevel] = useState('medium')
  const [industry, setIndustry] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<QuickWorkResult | null>(loadResult)
  const [progress, setProgress] = useState('')
  const [progressPercent, setProgressPercent] = useState(0)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [copied, setCopied] = useState<'title' | 'desc' | null>(null)
  const pollRef = useRef<any>(null)

  // Persist result to localStorage whenever it changes
  useEffect(() => { saveResult(result) }, [result])

  // Cleanup polling on unmount
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  const pollTask = useCallback((id: string) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const r = await client.get(`/quick-work/task/${id}`)
        if (r.data.success) {
          const task = r.data.data
          setProgress(task.step || '处理中...')
          setProgressPercent(task.progress || 0)

          if (task.status === 'completed') {
            clearInterval(pollRef.current)
            pollRef.current = null
            setResult(task.result)
            setTaskId(null)
            setLoading(false)
            setProgress('')
            message.success(task.message || '完成！')
          } else if (task.status === 'failed') {
            clearInterval(pollRef.current)
            pollRef.current = null
            message.error(task.error || '任务失败')
            setTaskId(null)
            setLoading(false)
            setProgress('')
          }
        }
      } catch {
        // keep polling
      }
    }, 2000)
  }, [])

  const handleRun = async () => {
    if (!url.trim()) {
      message.warning('请输入笔记链接')
      return
    }
    setLoading(true)
    setResult(null)
    setProgressPercent(5)
    setProgress('正在提交任务...')

    try {
      const resp = await client.post('/quick-work/run-async', {
        url: url.trim(),
        style,
        ratio,
        debate,
        image_level: imageLevel,
        industry,
      })
      if (resp.data.success && resp.data.task_id) {
        setTaskId(resp.data.task_id)
        setProgress('任务已提交，等待处理...')
        pollTask(resp.data.task_id)
      } else {
        message.error(resp.data.message || '提交失败')
        setLoading(false)
        setProgress('')
      }
    } catch (e: any) {
      message.error(e.response?.data?.message || e.message || '请求失败')
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

  // ── 辩论方案选择 ──────────────────────────────────────────────────
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null)

  const selectDebateVersion = (idx: number) => {
    if (!result?.debate?.all_versions) return
    const version = result.debate.all_versions[idx]
    if (!version) return
    setSelectedVersion(idx)
    // Update rewritten content with selected version
    setResult({
      ...result,
      rewritten: {
        title: version.title,
        desc: version.desc,
        agent_name: version.agent_name,
        agent_emoji: version.agent_emoji,
      },
    })
    message.success(`已选择方案 ${idx + 1}: ${version.agent_name || '方案' + (idx + 1)}`)
  }

  const rewrittenTitle = result?.rewritten?.title || ''
  const rewrittenDesc = result?.rewritten?.desc || ''

  // ── 内容检测状态 ──────────────────────────────────────────────────
  const [checkTab, setCheckTab] = useState<string>('banned')
  const [bannedLoading, setBannedLoading] = useState(false)
  const [bannedResult, setBannedResult] = useState<any>(null)
  const [aiDetectLoading, setAiDetectLoading] = useState(false)
  const [aiDetectResult, setAiDetectResult] = useState<any>(null)
  const [aiOriginality, setAiOriginality] = useState<any>(null)
  const [checkTitle, setCheckTitle] = useState('')
  const [checkContent, setCheckContent] = useState('')

  // Auto-fill check content when result changes
  useEffect(() => {
    if (result?.rewritten) {
      setCheckTitle(result.rewritten.title || '')
      setCheckContent(result.rewritten.desc || '')
    }
  }, [result?.rewritten?.title, result?.rewritten?.desc])

  const runBannedCheck = async () => {
    const titleToCheck = checkTitle.trim() || rewrittenTitle
    const contentToCheck = checkContent.trim() || rewrittenDesc
    if (!titleToCheck && !contentToCheck) { message.warning('请输入要检测的内容'); return }
    setBannedLoading(true)
    try {
      const r = await client.post('/content-check/full', { title: titleToCheck, content: contentToCheck })
      if (r.data.success) {
        setBannedResult(r.data.data)
        message.success('违禁词检测完成')
      } else {
        message.error(r.data.message || '检测失败')
      }
    } catch (e: any) {
      message.error('违禁词检测请求失败: ' + (e.response?.data?.detail || e.response?.data?.message || e.message || '请检查后端服务'))
    }
    setBannedLoading(false)
  }

  const runAICheck = async () => {
    const text = `${checkTitle.trim() || rewrittenTitle} ${checkContent.trim() || rewrittenDesc}`.trim()
    if (!text) { message.warning('请输入要检测的内容'); return }
    setAiDetectLoading(true)
    try {
      const detectR = await client.post('/ai-check/detect', { text })
      if (detectR.data.success) {
        setAiDetectResult(detectR.data.data)
      }
      try {
        const origR = await client.post('/ai-check/originality', { text })
        if (origR.data.success) {
          setAiOriginality(origR.data.data)
        }
      } catch {}
      message.success('AI味检测完成')
    } catch (e: any) {
      message.error('AI检测请求失败: ' + (e.response?.data?.detail || e.response?.data?.message || e.message || '请检查后端服务'))
    }
    setAiDetectLoading(false)
  }

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
    } catch (e: any) {
      message.error('保存草稿失败: ' + (e.response?.data?.message || e.message || '未知错误'))
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
    } catch (e: any) {
      message.error('发布失败: ' + (e.response?.data?.message || e.message || '未知错误'))
    }
    setPublishing(false)
  }

  // Helper: resolve image URL
  const resolveImageUrl = (url: string) => {
    if (!url) return ''
    if (url.startsWith('http')) return url
    if (url.startsWith('/data/')) return url
    return `/api/images/proxy?url=${encodeURIComponent(url)}`
  }

  // Helper: download image from URL
  const downloadImage = async (url: string, filename: string) => {
    try {
      const response = await fetch(url)
      const blob = await response.blob()
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(link.href)
      message.success(`已下载 ${filename}`)
    } catch {
      message.error('下载失败，请右键图片另存为')
    }
  }

  // Build debate scores summary for Collapse label
  const getDebateScoresSummary = (): string => {
    if (!result?.debate?.scores) return ''
    const entries = Object.entries(result.debate.scores)
    if (entries.length === 0) return ''
    return entries.map(([k, v]) => `${k}: ${getScoreTotal(v)}分`).join(', ')
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
            <div style={{ minWidth: 200 }}>
              <Text strong>🏢 行业</Text>
              <Select
                allowClear
                placeholder="选择行业（可选）"
                options={INDUSTRIES.map(s => ({ label: s, value: s }))}
                value={industry || undefined}
                onChange={(v) => setIndustry(v || '')}
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
            {loading ? '处理中...' : '一键开始'}
          </Button>
        </Space>
      </Card>

      {loading && progress && (
        <Card style={{ marginBottom: 24 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Space>
              <Spin size="small" />
              <Text>{progress}</Text>
            </Space>
            <Progress percent={progressPercent} status="active" />
          </Space>
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

              {/* ── 辩论结果 ─────────────────────────────── */}
              {result.debate && (
                <Collapse style={{ marginTop: 16 }} ghost items={[
                  {
                    key: 'debate',
                    label: (
                      <Space>
                        <span>🏆 辩论评审</span>
                        {getDebateScoresSummary() && (
                          <Tag color="gold">评分: {getDebateScoresSummary()}</Tag>
                        )}
                        {result.debate.winner?.agent_name && (
                          <Tag color="red">推荐: {result.debate.winner.agent_emoji} {result.debate.winner.agent_name}</Tag>
                        )}
                      </Space>
                    ),
                    children: (
                      <div style={{ padding: '8px 0' }}>
                        {result.debate.reasoning && (
                          <Paragraph style={{ color: '#666', marginBottom: 12 }}>
                            {result.debate.reasoning}
                          </Paragraph>
                        )}
                        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
                          💡 点击"选择此方案"可切换到你偏好的版本，上方标题/正文会自动更新
                        </Text>
                        {Array.isArray(result.debate.all_versions) && result.debate.all_versions.map((v: any, i: number) => {
                          if (!v) return null
                          const debate = result.debate!
                          const isSelected = (selectedVersion === i) ||
                            (selectedVersion === null && debate.winner && v.agent === debate.winner.agent)
                          const scoreVal = debate.scores?.[v.agent]
                          const totalScore = getScoreTotal(scoreVal)
                          return (
                            <Card key={i} size="small" style={{
                              marginBottom: 8,
                              border: isSelected ? '2px solid #ff4757' : '1px solid #f0f0f0',
                              background: isSelected ? '#fff7f7' : '#fafafa',
                            }}
                              title={
                                <Space>
                                  <span>{v.agent_emoji || ''} {v.agent_name || `方案${i + 1}`}</span>
                                  {isSelected && <Tag color="red">当前选中</Tag>}
                                  {debate.winner && v.agent === debate.winner.agent && <Tag color="gold">AI推荐</Tag>}
                                </Space>
                              }
                              extra={
                                <Button
                                  type={isSelected ? 'primary' : 'default'}
                                  size="small"
                                  icon={isSelected ? <StarFilled /> : <StarOutlined />}
                                  onClick={() => selectDebateVersion(i)}
                                  disabled={isSelected}
                                >
                                  {isSelected ? '已选择' : '选择此方案'}
                                </Button>
                              }
                            >
                              <Text strong style={{ display: 'block', marginBottom: 4 }}>{v.title || '(无标题)'}</Text>
                              <Paragraph type="secondary" ellipsis={{ rows: 3 }} style={{ marginBottom: 4 }}>
                                {v.desc || '(无正文)'}
                              </Paragraph>
                              {totalScore > 0 && (
                                <>
                                  <Tag color="blue">总分: {totalScore}</Tag>
                                  <ScoreBreakdown scoreValue={scoreVal} />
                                </>
                              )}
                            </Card>
                          )
                        })}
                      </div>
                    ),
                  },
                ]} />
              )}
            </Card>
          )}

          {/* 图片处理 */}
          {result.images_processed && result.images_processed.length > 0 && (
            <Card
              title={`🖼️ 图片降重 (${result.images_processed.filter(i => i.processed).length}/${result.images_processed.length})`}
              extra={
                result.images_processed.filter(i => i.processed).length > 0 && (
                  <Button
                    type="primary"
                    size="small"
                    icon={<DownloadOutlined />}
                    onClick={() => {
                      result.images_processed.forEach((img, i) => {
                        if (img.processed) {
                          downloadImage(resolveImageUrl(img.processed), `降重_${i + 1}.png`)
                        }
                      })
                    }}
                  >
                    下载全部
                  </Button>
                )
              }
            >
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {result.images_processed.map((img, i) => (
                  <div key={i} style={{ textAlign: 'center' }}>
                    <div style={{ display: 'flex', gap: 8 }}>
                      {img.original && (
                        <div>
                          <Text type="secondary" style={{ fontSize: 12 }}>原图</Text>
                          <Image
                            src={resolveImageUrl(img.original)}
                            width={120} height={120} style={{ objectFit: 'cover', borderRadius: 8 }}
                            fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
                            preview={{ mask: '查看大图' }}
                          />
                        </div>
                      )}
                      {img.processed && (
                        <div>
                          <Text type="secondary" style={{ fontSize: 12 }}>降重后</Text>
                          <div style={{ position: 'relative', display: 'inline-block' }}>
                            <Image
                              src={resolveImageUrl(img.processed)}
                              width={120} height={120} style={{ objectFit: 'cover', borderRadius: 8 }}
                              fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
                              preview={{ mask: '查看大图' }}
                            />
                            <Tooltip title="下载">
                              <Button
                                type="primary"
                                size="small"
                                icon={<DownloadOutlined />}
                                style={{ position: 'absolute', bottom: 4, right: 4, opacity: 0.9 }}
                                onClick={() => downloadImage(resolveImageUrl(img.processed!), `降重_${i + 1}.png`)}
                              />
                            </Tooltip>
                          </div>
                        </div>
                      )}
                      {!img.processed && (
                        <div>
                          <Text type="secondary" style={{ fontSize: 12 }}>降重后</Text>
                          <div style={{ width: 120, height: 120, background: '#f5f5f5', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <Text type="danger" style={{ fontSize: 11 }}>{img.error || '降重失败'}</Text>
                          </div>
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
          {(!result.images_processed || result.images_processed.length === 0) && result.images_original && result.images_original.length > 0 && (
            <Card
              title={`🖼️ 原图 (${result.images_original.length}张)`}
              extra={
                <Button
                  size="small"
                  icon={<DownloadOutlined />}
                  onClick={() => {
                    result.images_original.forEach((img, i) => {
                      downloadImage(resolveImageUrl(img), `原图_${i + 1}.png`)
                    })
                  }}
                >
                  下载全部
                </Button>
              }
            >
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {result.images_original.map((img, i) => (
                  <div key={i} style={{ position: 'relative', display: 'inline-block' }}>
                    <Image
                      src={resolveImageUrl(img)}
                      width={150} height={150} style={{ objectFit: 'cover', borderRadius: 8 }}
                      fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
                      preview={{ mask: '查看大图' }}
                    />
                    <Tooltip title="下载">
                      <Button
                        type="primary"
                        size="small"
                        icon={<DownloadOutlined />}
                        style={{ position: 'absolute', bottom: 4, right: 4, opacity: 0.9 }}
                        onClick={() => downloadImage(resolveImageUrl(img), `原图_${i + 1}.png`)}
                      />
                    </Tooltip>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* 内容检测 — 一站式内嵌，可编辑文本 */}
          <Card title="🔍 内容检测" size="small">
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <Text type="secondary">
                检测改写后的内容，也可以编辑后重新检测
              </Text>
              <div>
                <Text strong>检测标题：</Text>
                <Input
                  value={checkTitle}
                  onChange={e => setCheckTitle(e.target.value)}
                  placeholder="输入要检测的标题"
                  style={{ marginTop: 4 }}
                />
              </div>
              <div>
                <Text strong>检测正文：</Text>
                <TextArea
                  rows={4}
                  value={checkContent}
                  onChange={e => setCheckContent(e.target.value)}
                  placeholder="输入要检测的正文内容"
                  style={{ marginTop: 4 }}
                />
              </div>

              <Tabs activeKey={checkTab} onChange={setCheckTab} items={[
                {
                  key: 'banned',
                  label: <span><SafetyCertificateOutlined /> 违禁词检测</span>,
                  children: (
                    <Space direction="vertical" style={{ width: '100%' }} size="middle">
                      <Button type="primary" onClick={runBannedCheck} loading={bannedLoading}>
                        开始违禁词检测
                      </Button>
                      {bannedResult && (
                        <>
                          <Row gutter={16}>
                            <Col span={6}>
                              <Card size="small">
                                <Statistic title="安全评分" value={bannedResult.summary?.safety_score ?? '-'} suffix="分"
                                  valueStyle={{ color: (bannedResult.summary?.safety_score ?? 0) >= 80 ? '#3f8600' : '#cf1322' }} />
                              </Card>
                            </Col>
                            <Col span={6}>
                              <Card size="small">
                                <Statistic title="违禁词" value={bannedResult.summary?.total_issues ?? 0}
                                  valueStyle={{ color: '#cf1322' }} />
                              </Card>
                            </Col>
                            <Col span={6}>
                              <Card size="small">
                                <Statistic title="严重" value={bannedResult.summary?.critical ?? 0}
                                  prefix={<ExclamationCircleOutlined />}
                                  valueStyle={{ color: '#cf1322' }} />
                              </Card>
                            </Col>
                            <Col span={6}>
                              <Card size="small">
                                <Statistic title="警告" value={bannedResult.summary?.warning ?? 0}
                                  prefix={<WarningOutlined />}
                                  valueStyle={{ color: '#fa8c16' }} />
                              </Card>
                            </Col>
                          </Row>
                          {bannedResult.suggestions && bannedResult.suggestions.length > 0 && (
                            <Card title="替换建议" size="small">
                              <List size="small"
                                dataSource={bannedResult.suggestions}
                                renderItem={(item: any) => (
                                  <List.Item>
                                    <Space>
                                      <Tag color={item.severity === 'critical' ? 'red' : 'orange'}>{item.severity}</Tag>
                                      <Text delete>{item.word}</Text>
                                      <Text type="secondary">→ {item.replacements?.[0]}</Text>
                                    </Space>
                                  </List.Item>
                                )}
                              />
                            </Card>
                          )}
                          {bannedResult.banned_words && bannedResult.banned_words.found && bannedResult.banned_words.found.length === 0 && (
                            <Space>
                              <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 24 }} />
                              <Text strong>恭喜！未检测到违禁词，内容安全</Text>
                            </Space>
                          )}
                        </>
                      )}
                    </Space>
                  ),
                },
                {
                  key: 'ai',
                  label: <span><RobotOutlined /> AI味检测</span>,
                  children: (
                    <Space direction="vertical" style={{ width: '100%' }} size="middle">
                      <Button type="primary" onClick={runAICheck} loading={aiDetectLoading}>
                        开始AI味检测
                      </Button>
                      {aiDetectResult && (
                        <>
                          <Row gutter={16}>
                            <Col span={8}>
                              <Card size="small" style={{ textAlign: 'center' }}>
                                <Progress
                                  type="dashboard"
                                  percent={aiDetectResult.score ?? 0}
                                  strokeColor={(aiDetectResult.score ?? 0) <= 30 ? '#52c41a' : (aiDetectResult.score ?? 0) <= 60 ? '#faad14' : '#ff4d4f'}
                                  format={() => (
                                    <div>
                                      <div style={{ fontSize: 24, fontWeight: 'bold', color: (aiDetectResult.score ?? 0) <= 30 ? '#52c41a' : (aiDetectResult.score ?? 0) <= 60 ? '#faad14' : '#ff4d4f' }}>
                                        {aiDetectResult.score ?? 0}
                                      </div>
                                      <div style={{ fontSize: 12, color: '#999' }}>AI味指数</div>
                                    </div>
                                  )}
                                />
                                <div style={{ marginTop: 8 }}>
                                  <Tag color={(aiDetectResult.score ?? 0) <= 30 ? 'green' : (aiDetectResult.score ?? 0) <= 60 ? 'orange' : 'red'}>
                                    {aiDetectResult.level || '未知'}
                                  </Tag>
                                </div>
                              </Card>
                            </Col>
                            <Col span={16}>
                              <Card size="small" title="AI味词汇">
                                {!aiDetectResult.details || aiDetectResult.details.length === 0 ? (
                                  <Empty description="未检测到AI味词汇" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                                ) : (
                                  <div style={{ maxHeight: 150, overflowY: 'auto' }}>
                                    {aiDetectResult.details.map((d: any, i: number) => (
                                      <Tag key={i} color="red" style={{ margin: 2 }}>
                                        <Tooltip title={d.type}>{d.word}</Tooltip>
                                      </Tag>
                                    ))}
                                  </div>
                                )}
                              </Card>
                            </Col>
                          </Row>
                          {aiOriginality && (
                            <Card size="small" title="原创度评估">
                              <Row gutter={16}>
                                <Col span={8}>
                                  <Progress
                                    type="circle"
                                    percent={aiOriginality.score ?? 0}
                                    strokeColor={(aiOriginality.score ?? 0) >= 70 ? '#52c41a' : (aiOriginality.score ?? 0) >= 40 ? '#faad14' : '#ff4d4f'}
                                    format={() => <span>{aiOriginality.score ?? 0}分</span>}
                                  />
                                </Col>
                                <Col span={16}>
                                  <Space direction="vertical">
                                    <Text>字符多样性: {aiOriginality.details?.unique_ratio || '-'}</Text>
                                    <Text>平均句长: {aiOriginality.details?.avg_sentence_len || '-'}字</Text>
                                    <Text>重复词数: {aiOriginality.details?.repeated_words || '-'}</Text>
                                  </Space>
                                </Col>
                              </Row>
                            </Card>
                          )}
                        </>
                      )}
                    </Space>
                  ),
                },
              ]} />
            </Space>
          </Card>

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
