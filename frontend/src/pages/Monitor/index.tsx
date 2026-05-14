import React, { useEffect, useState } from 'react'
import { App,  Card, Table, Button, Space, Typography, Tag, Modal, Form, Input, Select, Switch, Popconfirm, Drawer, Row, Col, Statistic, Divider, Empty } from 'antd'
import {
  PlusOutlined, PlayCircleOutlined, DeleteOutlined, EyeOutlined,
  BarChartOutlined, SwapOutlined,
} from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text, Paragraph } = Typography

export default function MonitorPage() {
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [snapDrawer, setSnapDrawer] = useState<any>(null)
  const [snapshots, setSnapshots] = useState<any[]>([])
  const [comparison, setComparison] = useState<any>(null)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const r = await client.get('/monitor')
      setItems(r.data.data || [])
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const onCreate = async (values: any) => {
    await client.post('/monitor', { ...values, ai_analysis: values.ai_analysis || false })
    message.success('监控已创建')
    setModalOpen(false)
    form.resetFields()
    load()
  }

  const onCheck = async (id: number) => {
    message.loading('正在检查...')
    const r = await client.post(`/monitor/${id}/check`)
    if (r.data.success) message.success('检查完成')
    else message.warning(r.data.message)
    load()
  }

  const onViewSnaps = async (item: any) => {
    setSnapDrawer(item)
    setComparison(null)
    try {
      const r = await client.get(`/monitor/${item.id}/snapshots`)
      setSnapshots(r.data.data || [])
    } catch { setSnapshots([]) }
  }

  const onCompare = async () => {
    if (!snapDrawer) return
    try {
      const r = await client.get(`/monitor/analysis/compare`, { params: { item_id: snapDrawer.id } })
      if (r.data.success && r.data.data) {
        setComparison(r.data.data)
        message.success('对比完成')
      } else {
        message.info(r.data.message || '需要至少两次快照')
      }
    } catch { message.error('对比失败') }
  }

  const onDelete = async (id: number) => {
    await client.delete(`/monitor/${id}`)
    message.success('已删除')
    load()
  }

  const typeMap: Record<string, { label: string; color: string }> = {
    keyword: { label: '关键词', color: 'blue' },
    account: { label: '账号', color: 'purple' },
    brand: { label: '品牌', color: 'orange' },
    url: { label: 'URL', color: 'cyan' },
  }

  const renderSnapshot = (data: any) => {
    if (!data) return null
    const parsed = typeof data === 'string' ? JSON.parse(data) : data

    // 关键词监控结果
    if (parsed.type === 'keyword' && parsed.notes) {
      return (
        <div>
          <Row gutter={16} style={{ marginBottom: 12 }}>
            <Col span={8}><Statistic title="笔记数" value={parsed.count || parsed.notes.length} /></Col>
            <Col span={8}><Statistic title="平均点赞" value={parsed.ai_analysis?.avg_likes || '-'} /></Col>
            <Col span={8}><Statistic title="最高点赞" value={parsed.ai_analysis?.max_likes || '-'} /></Col>
          </Row>
          {parsed.ai_analysis?.top_note && (
            <Paragraph type="secondary">🔥 热门标题：{parsed.ai_analysis.top_note}</Paragraph>
          )}
          <Table size="small" dataSource={parsed.notes} rowKey="note_id" pagination={false}
            columns={[
              { title: '标题', dataIndex: 'title', ellipsis: true },
              { title: '作者', dataIndex: 'author', width: 100 },
              { title: '类型', dataIndex: 'type', width: 60, render: (v: string) =>
                <Tag color={v === 'video' ? 'red' : 'blue'}>{v === 'video' ? '视频' : '图文'}</Tag> },
              { title: '点赞', dataIndex: 'likes', width: 70 },
              { title: '收藏', dataIndex: 'collects', width: 70 },
              { title: '评论', dataIndex: 'comments', width: 70 },
            ]} />
        </div>
      )
    }

    // 账号监控结果
    if (parsed.type === 'account' && parsed.users) {
      return (
        <div>
          <Statistic title="搜索到的用户" value={parsed.count} style={{ marginBottom: 12 }} />
          <Table size="small" dataSource={parsed.users} rowKey="user_id" pagination={false}
            columns={[
              { title: '昵称', dataIndex: 'nickname' },
              { title: '简介', dataIndex: 'desc', ellipsis: true },
              { title: '粉丝', dataIndex: 'fans', width: 100 },
            ]} />
        </div>
      )
    }

    // URL 监控结果
    if (parsed.type === 'url') {
      return (
        <div>
          <Paragraph strong>📌 {parsed.title || '笔记详情'}</Paragraph>
          {parsed.desc && <Paragraph type="secondary">{parsed.desc}</Paragraph>}
          <Row gutter={16}>
            <Col span={8}><Statistic title="点赞" value={parsed.likes || 0} /></Col>
            <Col span={8}><Statistic title="收藏" value={parsed.collects || 0} /></Col>
            <Col span={8}><Statistic title="评论" value={parsed.comments || 0} /></Col>
          </Row>
          {parsed.ai_analysis && (
            <div style={{ marginTop: 12 }}>
              <Divider />
              <Text strong>📊 AI 分析</Text>
              <Row gutter={16} style={{ marginTop: 8 }}>
                <Col span={8}><Statistic title="互动分" value={parsed.ai_analysis.engagement_score} /></Col>
                <Col span={8}><Statistic title="赞藏比" value={parsed.ai_analysis.like_collect_ratio} /></Col>
                <Col span={8}><Statistic title="互动级别" value={parsed.ai_analysis.interaction_level} /></Col>
              </Row>
            </div>
          )}
        </div>
      )
    }

    // 错误或未知
    if (parsed.error) return <Text type="danger">❌ {parsed.error}</Text>
    return <pre style={{ fontSize: 12, maxHeight: 300, overflow: 'auto' }}>{JSON.stringify(parsed, null, 2)}</pre>
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>竞品内容深度分析</Title>
          <Text type="secondary">关键词/账号/URL 监控 + AI 数据分析 + 趋势对比</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新建监控</Button>
      </div>
      <Card>
        <Table dataSource={items} rowKey="id" loading={loading} pagination={false}
          columns={[
            { title: 'ID', dataIndex: 'id', width: 50 },
            { title: '名称', dataIndex: 'name', width: 140 },
            { title: '类型', dataIndex: 'monitor_type', width: 80, render: (v: string) =>
              <Tag color={typeMap[v]?.color || 'default'}>{typeMap[v]?.label || v}</Tag> },
            { title: '目标', dataIndex: 'target', ellipsis: true },
            { title: '间隔(分)', dataIndex: 'interval_minutes', width: 80 },
            { title: '状态', dataIndex: 'is_active', width: 70, render: (v: boolean) =>
              <Tag color={v ? 'green' : 'default'}>{v ? '运行中' : '暂停'}</Tag> },
            { title: '上次检查', dataIndex: 'last_check', width: 140, render: (v: string) => v ? v.slice(0, 16) : '-' },
            { title: '操作', width: 180, render: (_: any, r: any) => (
              <Space size="small">
                <Button size="small" icon={<PlayCircleOutlined />} onClick={() => onCheck(r.id)}>检查</Button>
                <Button size="small" icon={<EyeOutlined />} onClick={() => onViewSnaps(r)}>数据</Button>
                <Popconfirm title="删除？" onConfirm={() => onDelete(r.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            )},
          ]} />
      </Card>

      {/* 新建监控弹窗 */}
      <Modal title="新建竞品监控" open={modalOpen} onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()} width={480}>
        <Form form={form} onFinish={onCreate} layout="vertical" initialValues={{ monitor_type: 'keyword', interval_minutes: 60, ai_analysis: true }}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="例如：竞品XX品牌监控" />
          </Form.Item>
          <Form.Item name="monitor_type" label="监控类型">
            <Select options={[
              { value: 'keyword', label: '🔍 关键词 — 监控搜索结果' },
              { value: 'account', label: '👤 账号 — 监控用户动态' },
              { value: 'url', label: '🔗 URL — 监控笔记数据变化' },
              { value: 'brand', label: '🏷️ 品牌 — 品牌声量监控（开发中）' },
            ]} />
          </Form.Item>
          <Form.Item name="target" label="监控目标" rules={[{ required: true }]}
            extra="关键词: 输入搜索词 | 账号: 输入用户ID | URL: 粘贴笔记链接">
            <Input placeholder="关键词/用户ID/笔记链接" />
          </Form.Item>
          <Form.Item name="interval_minutes" label="检查间隔(分钟)">
            <Input type="number" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 快照数据抽屉 */}
      <Drawer title={snapDrawer?.name || '监控数据'} open={!!snapDrawer}
        onClose={() => { setSnapDrawer(null); setSnapshots([]); setComparison(null) }}
        width={700}
        extra={<Button icon={<SwapOutlined />} onClick={onCompare} size="small">趋势对比</Button>}>
        {/* 趋势对比 */}
        {comparison && (
          <Card size="small" style={{ marginBottom: 16, background: '#f6ffed' }}
            title="📊 趋势对比（最近两次快照）">
            <Row gutter={16}>
              <Col span={12}><Text type="secondary">上次检查: {comparison.prev_time?.slice(0, 16)}</Text></Col>
              <Col span={12}><Text type="secondary">本次检查: {comparison.curr_time?.slice(0, 16)}</Text></Col>
            </Row>
            <Divider style={{ margin: '8px 0' }} />
            <Row gutter={16}>
              {Object.entries(comparison.changes || {}).map(([key, val]: [string, any]) => (
                <Col span={8} key={key}>
                  <Statistic
                    title={key.replace(/_/g, ' ')}
                    value={val}
                    valueStyle={{ color: val > 0 ? '#52c41a' : val < 0 ? '#ff4757' : '#666' }}
                    prefix={val > 0 ? '↑' : val < 0 ? '↓' : ''}
                  />
                </Col>
              ))}
            </Row>
          </Card>
        )}

        {/* 历史快照列表 */}
        {snapshots.map((s, i) => (
          <Card key={s.id} size="small" style={{ marginBottom: 8 }}
            title={`快照 #${i + 1}`}
            extra={<Text type="secondary" style={{ fontSize: 12 }}>{s.created_at}</Text>}>
            {renderSnapshot(s.data_json)}
          </Card>
        ))}
        {!snapshots.length && <Empty description="暂无监控数据，请先执行检查" />}
      </Drawer>
    </div>
  )
}
