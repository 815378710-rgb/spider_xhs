import React, { useState } from 'react'
import { Card, Typography, Space, Button, Input, Tabs, Tag, Progress, List, Statistic, Row, Col, message, Tooltip, Empty } from 'antd'
import { SafetyCertificateOutlined, RobotOutlined, CheckCircleOutlined, WarningOutlined, ExclamationCircleOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

function BannedWordsTab() {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  const runCheck = async () => {
    const text = `${title} ${content}`.trim()
    if (!text) { message.warning('请输入要检测的内容'); return }
    setLoading(true)
    try {
      const r = await client.post('/content-check/full', { title, content })
      if (r.data.success) setResult(r.data.data)
      else message.error(r.data.message)
    } catch (e: any) {
      message.error('检测失败: ' + (e.response?.data?.message || e.message))
    }
    setLoading(false)
  }

  const applyReplacement = (original: string, replacement: string) => {
    setContent(prev => prev.replace(original, replacement))
    message.success(`已替换: ${original} → ${replacement}`)
  }

  const replaceAll = () => {
    if (!result?.cleaned_text) return
    setContent(result.cleaned_text)
    message.success('已应用所有替换建议')
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <div>
        <Text strong>标题</Text>
        <Input placeholder="输入笔记标题" value={title} onChange={e => setTitle(e.target.value)} style={{ marginTop: 4 }} />
      </div>
      <div>
        <Text strong>正文</Text>
        <TextArea rows={6} placeholder="输入笔记正文" value={content} onChange={e => setContent(e.target.value)} />
      </div>
      <Button type="primary" onClick={runCheck} loading={loading}>开始检测</Button>

      {result && (
        <>
          <Row gutter={16}>
            <Col span={6}>
              <Card size="small">
                <Statistic title="安全评分" value={result.summary.safety_score} suffix="分"
                  valueStyle={{ color: result.summary.safety_score >= 80 ? '#3f8600' : '#cf1322' }} />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic title="违禁词总数" value={result.summary.total_issues}
                  valueStyle={{ color: '#cf1322' }} />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic title="严重问题" value={result.summary.critical}
                  prefix={<ExclamationCircleOutlined />}
                  valueStyle={{ color: '#cf1322' }} />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic title="警告" value={result.summary.warning}
                  prefix={<WarningOutlined />}
                  valueStyle={{ color: '#fa8c16' }} />
              </Card>
            </Col>
          </Row>

          {result.suggestions.length > 0 && (
            <Card title="替换建议" size="small" extra={<Button size="small" onClick={replaceAll}>一键替换全部</Button>}>
              <List
                dataSource={result.suggestions}
                renderItem={(item: any) => (
                  <List.Item
                    actions={item.replacements.filter((r: string) => r !== '(请自行替换)').map((r: string) => (
                      <Button size="small" type="link" onClick={() => applyReplacement(item.word, r)}>
                        {r}
                      </Button>
                    ))}
                  >
                    <List.Item.Meta
                      title={
                        <Space>
                          <Tag color={item.severity === 'critical' ? 'red' : 'orange'}>{item.severity}</Tag>
                          <Text delete>{item.word}</Text>
                          <Text type="secondary">→ {item.replacements[0]}</Text>
                        </Space>
                      }
                      description={<Text type="secondary">{item.category}</Text>}
                    />
                  </List.Item>
                )}
              />
            </Card>
          )}

          {result.banned_words.found.length === 0 && (
            <Card>
              <Space>
                <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 24 }} />
                <Text strong>恭喜！未检测到违禁词，内容安全</Text>
              </Space>
            </Card>
          )}
        </>
      )}
    </Space>
  )
}

function AICheckTab() {
  const [text, setText] = useState('')
  const [detecting, setDetecting] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [detectResult, setDetectResult] = useState<any>(null)
  const [originality, setOriginality] = useState<any>(null)
  const [removedText, setRemovedText] = useState('')

  const runDetect = async () => {
    if (!text.trim()) { message.warning('请输入要检测的文本'); return }
    setDetecting(true)
    try {
      const [detectR, origR] = await Promise.all([
        client.post('/ai-check/detect', { text }),
        client.post('/ai-check/originality', { text }),
      ])
      if (detectR.data.success) setDetectResult(detectR.data.data)
      if (origR.data.success) setOriginality(origR.data.data)
    } catch (e: any) {
      message.error('检测失败: ' + (e.response?.data?.message || e.message))
    }
    setDetecting(false)
  }

  const runRemove = async () => {
    if (!text.trim()) { message.warning('请输入要处理的文本'); return }
    setRemoving(true)
    try {
      const r = await client.post('/ai-check/remove', { text })
      if (r.data.success) {
        setRemovedText(r.data.data.text)
        message.success('去AI味完成')
      } else {
        message.error(r.data.message)
      }
    } catch (e: any) {
      message.error('去AI味失败: ' + (e.response?.data?.message || e.message))
    }
    setRemoving(false)
  }

  const scoreColor = (score: number) => score <= 30 ? '#52c41a' : score <= 60 ? '#faad14' : '#ff4d4f'

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <div>
        <Text strong>输入文本</Text>
        <TextArea rows={6} placeholder="粘贴要检测的文案内容" value={text} onChange={e => setText(e.target.value)} />
      </div>
      <Space>
        <Button type="primary" onClick={runDetect} loading={detecting}>AI味检测</Button>
        <Button onClick={runRemove} loading={removing}>一键去AI味</Button>
      </Space>

      {detectResult && (
        <Row gutter={16}>
          <Col span={8}>
            <Card size="small" style={{ textAlign: 'center' }}>
              <Progress
                type="dashboard"
                percent={detectResult.score}
                strokeColor={scoreColor(detectResult.score)}
                format={() => (
                  <div>
                    <div style={{ fontSize: 24, fontWeight: 'bold', color: scoreColor(detectResult.score) }}>
                      {detectResult.score}
                    </div>
                    <div style={{ fontSize: 12, color: '#999' }}>AI味指数</div>
                  </div>
                )}
              />
              <div style={{ marginTop: 8 }}>
                <Tag color={detectResult.score <= 30 ? 'green' : detectResult.score <= 60 ? 'orange' : 'red'}>
                  {detectResult.level}
                </Tag>
              </div>
            </Card>
          </Col>
          <Col span={16}>
            <Card size="small" title="AI味词汇">
              {detectResult.details.length === 0 ? (
                <Empty description="未检测到AI味词汇" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                  {detectResult.details.map((d: any, i: number) => (
                    <Tag key={i} color="red" style={{ margin: 2 }}>
                      <Tooltip title={d.type}>{d.word}</Tooltip>
                    </Tag>
                  ))}
                </div>
              )}
            </Card>
            {detectResult.suggestions.length > 0 && (
              <Card size="small" title="改进建议" style={{ marginTop: 8 }}>
                <List size="small" dataSource={detectResult.suggestions}
                  renderItem={(s: string) => <List.Item>{s}</List.Item>} />
              </Card>
            )}
          </Col>
        </Row>
      )}

      {originality && (
        <Card size="small" title="原创度评估">
          <Row gutter={16}>
            <Col span={8}>
              <Progress
                type="circle"
                percent={originality.score}
                strokeColor={originality.score >= 70 ? '#52c41a' : originality.score >= 40 ? '#faad14' : '#ff4d4f'}
                format={() => <span>{originality.score}分</span>}
              />
            </Col>
            <Col span={16}>
              <Space direction="vertical">
                <Text>字符多样性: {originality.details.unique_ratio}</Text>
                <Text>平均句长: {originality.details.avg_sentence_len}字</Text>
                <Text>重复词数: {originality.details.repeated_words}</Text>
              </Space>
            </Col>
          </Row>
        </Card>
      )}

      {removedText && (
        <Card title="去AI味结果" extra={
          <Button type="link" onClick={() => { setText(removedText); setRemovedText('') }}>
            应用到输入框
          </Button>
        }>
          <Paragraph style={{ whiteSpace: 'pre-wrap' }}>{removedText}</Paragraph>
        </Card>
      )}
    </Space>
  )
}

export default function ContentCheckPage() {
  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <Title level={4}>内容检测中心</Title>
      <Tabs defaultActiveKey="banned" items={[
        {
          key: 'banned',
          label: <span><SafetyCertificateOutlined /> 违禁词检测</span>,
          children: <BannedWordsTab />,
        },
        {
          key: 'ai',
          label: <span><RobotOutlined /> AI味检测</span>,
          children: <AICheckTab />,
        },
      ]} />
    </div>
  )
}
