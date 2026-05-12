import React, { useEffect, useState } from 'react'
import { Card, Table, Button, Space, Typography, Tag, Modal, Form, Input, Switch, message, Popconfirm, Drawer, Row, Col, Statistic, Empty } from 'antd'
import {
  PlusOutlined, PlayCircleOutlined, DeleteOutlined, PauseCircleOutlined,
  FileTextOutlined, CheckCircleOutlined, CloseCircleOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text } = Typography

export default function AutomationPage() {
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [logDrawer, setLogDrawer] = useState<any>(null)
  const [logs, setLogs] = useState<any[]>([])
  const [stats, setStats] = useState<any>({})
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const [listRes, statsRes] = await Promise.allSettled([
        client.get('/automation'),
        client.get('/automation/stats/summary'),
      ])
      if (listRes.status === 'fulfilled') setItems(listRes.value.data?.data || [])
      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data?.data || {})
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const onCreate = async (values: any) => {
    try {
      const config = JSON.stringify({
        rewrite: values.rewrite !== false,
        image_process: values.image_process || false,
        image_preset: values.image_preset || 'light',
        publish: values.publish !== false,
        max_retries: values.max_retries || 1,
      })
      await client.post('/automation', {
        name: values.name, keywords: values.keywords,
        schedule_cron: values.schedule_cron || '0 9 * * *',
        pipeline_config: config,
      })
      message.success('流水线已创建')
      setModalOpen(false)
      form.resetFields()
      load()
    } catch (e: any) {
      message.error('创建失败: ' + (e.response?.data?.message || e.message || '未知错误'))
    }
  }

  const onToggle = async (id: number) => {
    try {
      await client.post(`/automation/${id}/toggle`)
      load()
    } catch (e: any) {
      message.error('操作失败: ' + (e.response?.data?.message || e.message || '未知错误'))
    }
  }

  const onRun = async (id: number) => {
    try {
      await client.post(`/automation/${id}/run`)
      message.success('流水线已启动')
      load()
    } catch (e: any) {
      message.error('启动失败: ' + (e.response?.data?.message || e.message || '未知错误'))
    }
  }

  const onDelete = async (id: number) => {
    try {
      await client.delete(`/automation/${id}`)
      message.success('已删除')
      load()
    } catch (e: any) {
      message.error('删除失败: ' + (e.response?.data?.message || e.message || '未知错误'))
    }
  }

  const onViewLogs = async (item: any) => {
    setLogDrawer(item)
    try {
      const r = await client.get(`/automation/${item.id}/logs`, { params: { limit: 50 } })
      setLogs(r.data.data || [])
    } catch { setLogs([]) }
  }

  const onClearLogs = async () => {
    if (!logDrawer) return
    await client.delete(`/automation/${logDrawer.id}/logs`)
    setLogs([])
    message.success('日志已清空')
  }

  const stepLabels: Record<string, string> = {
    search: '🔍 搜索', rewrite: '✏️ 改写', image: '🖼️ 图片', publish: '📤 发布',
  }
  const statusColor: Record<string, string> = {
    success: 'green', failed: 'red', running: 'blue',
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            <ThunderboltOutlined /> AI Agent 全流程自动化
          </Title>
          <Text type="secondary">自动搜索 → AI改写 → 图片处理 → 发布，全流程自动执行</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新建流水线</Button>
      </div>

      {/* 统计概览 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card hoverable size="small">
            <Statistic title="流水线总数" value={stats.total_pipelines || 0}
              prefix={<FileTextOutlined />} valueStyle={{ color: '#1890ff' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable size="small">
            <Statistic title="总执行次数" value={stats.total_runs || 0}
              prefix={<ThunderboltOutlined />} valueStyle={{ color: '#722ed1' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable size="small">
            <Statistic title="成功笔记" value={stats.total_success || 0}
              prefix={<CheckCircleOutlined />} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable size="small">
            <Statistic title="失败次数" value={stats.total_failed || 0}
              prefix={<CloseCircleOutlined />} valueStyle={{ color: '#ff4757' }} />
          </Card>
        </Col>
      </Row>

      {/* 流水线列表 */}
      <Card>
        <Table dataSource={items} rowKey="id" loading={loading} pagination={false}
          columns={[
            { title: 'ID', dataIndex: 'id', width: 50 },
            { title: '名称', dataIndex: 'name', width: 160 },
            { title: '关键词', dataIndex: 'keywords', ellipsis: true },
            { title: 'Cron', dataIndex: 'schedule_cron', width: 110 },
            { title: '状态', dataIndex: 'is_active', width: 70, render: (v: boolean) =>
              <Tag color={v ? 'green' : 'default'}>{v ? '运行中' : '暂停'}</Tag> },
            { title: '执行/成功/失败', width: 120, render: (_: any, r: any) =>
              <span>{r.run_count || 0} / <span style={{ color: '#52c41a' }}>{r.success_count || 0}</span> / <span style={{ color: '#ff4757' }}>{r.fail_count || 0}</span></span> },
            { title: '上次运行', dataIndex: 'last_run', width: 140, render: (v: string) => v ? v.slice(0, 16) : '-' },
            { title: '操作', width: 220, render: (_: any, r: any) => (
              <Space size="small">
                <Button size="small" icon={<PlayCircleOutlined />} onClick={() => onRun(r.id)}>执行</Button>
                <Button size="small" icon={<FileTextOutlined />} onClick={() => onViewLogs(r)}>日志</Button>
                <Button size="small" icon={r.is_active ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                  onClick={() => onToggle(r.id)}>
                  {r.is_active ? '暂停' : '启用'}
                </Button>
                <Popconfirm title="确定删除？" onConfirm={() => onDelete(r.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            )},
          ]} />
      </Card>

      {/* 新建弹窗 */}
      <Modal title="新建自动化流水线" open={modalOpen} onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()} width={520}>
        <Form form={form} onFinish={onCreate} layout="vertical" initialValues={{
          rewrite: true, publish: true, image_process: false, image_preset: 'light', max_retries: 1,
        }}>
          <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
            <Input placeholder="例如：每日穿搭自动改写" />
          </Form.Item>
          <Form.Item name="keywords" label="搜索关键词（逗号分隔）" rules={[{ required: true }]}>
            <Input.TextArea rows={2} placeholder="穿搭分享, OOTD, 日常穿搭 ..." />
          </Form.Item>
          <Form.Item name="schedule_cron" label="执行时间（Cron）" initialValue="0 9 * * *"
            extra="每天9点=0 9 * * *，每周一10点=0 10 * * 1">
            <Input placeholder="0 9 * * *" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="rewrite" label="AI 改写" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="publish" label="自动发布" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="image_process" label="图片降重" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="max_retries" label="改写失败重试次数">
                <Input type="number" min={0} max={5} />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      {/* 执行日志抽屉 */}
      <Drawer title={`执行日志 — ${logDrawer?.name || ''}`} open={!!logDrawer}
        onClose={() => { setLogDrawer(null); setLogs([]) }} width={600}
        extra={<Button size="small" danger onClick={onClearLogs}>清空日志</Button>}>
        {logs.length > 0 ? logs.map((log) => (
          <Card key={log.id} size="small" style={{ marginBottom: 8 }}
            title={<Space>
              <Tag color={statusColor[log.status]}>{log.status === 'success' ? '✅' : log.status === 'failed' ? '❌' : '⏳'}</Tag>
              <span>{stepLabels[log.step] || log.step}</span>
              <Text type="secondary">关键词: {log.keyword}</Text>
            </Space>}
            extra={<Text type="secondary" style={{ fontSize: 12 }}>{log.created_at?.slice(0, 16)}</Text>}>
            <Text>{log.message}</Text>
            {log.duration_ms > 0 && <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>({log.duration_ms}ms)</Text>}
          </Card>
        )) : (
          <Empty description="暂无执行日志" />
        )}
      </Drawer>
    </div>
  )
}
