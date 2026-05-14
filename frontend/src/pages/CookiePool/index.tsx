import React, { useState, useEffect, useCallback } from 'react'
import {
  App, Card, Table, Button, Space, Typography, Tag, Modal, Input, message,
  Descriptions, Statistic, Row, Col, Popconfirm, Tooltip, Alert
} from 'antd'
import {
  ReloadOutlined, DeleteOutlined, PlusOutlined, CheckCircleOutlined,
  CloseCircleOutlined, SyncOutlined, SafetyCertificateOutlined,
  CopyOutlined, ThunderboltOutlined
} from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

interface CookieItem {
  index: number
  a1: string
  username: string
  is_valid: boolean
  last_used?: string
}

interface PoolInfo {
  pool: CookieItem[]
  total: number
  valid: number
  active_cookie: { a1: string; is_active: boolean }
}

export default function CookiePoolPage() {
  const { message } = App.useApp()
  const [info, setInfo] = useState<PoolInfo | null>(null)
  const [loading, setLoading] = useState(false)
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [newCookies, setNewCookies] = useState('')
  const [newUsername, setNewUsername] = useState('')
  const [addLoading, setAddLoading] = useState(false)
  const [validating, setValidating] = useState(false)
  const [autoUpdating, setAutoUpdating] = useState(false)

  const fetchInfo = useCallback(async () => {
    setLoading(true)
    try {
      const r = await client.get('/cookie/pool')
      if (r.data.success) {
        setInfo(r.data.data)
      }
    } catch (e: any) {
      message.error('获取 Cookie 池信息失败')
    }
    setLoading(false)
  }, [])

  useEffect(() => { fetchInfo() }, [fetchInfo])

  const handleValidateAll = async () => {
    setValidating(true)
    try {
      const r = await client.post('/cookie/pool/validate')
      if (r.data.success) {
        message.success('验证完成')
        fetchInfo()
      } else {
        message.warning(r.data.message || '验证失败')
      }
    } catch {
      message.error('验证请求失败')
    }
    setValidating(false)
  }

  const handleAutoUpdate = async () => {
    setAutoUpdating(true)
    try {
      const r = await client.post('/cookie/pool/auto-update')
      if (r.data.success) {
        message.success('自动更新完成')
        fetchInfo()
      } else {
        message.warning(r.data.message || '更新失败')
      }
    } catch {
      message.error('更新请求失败')
    }
    setAutoUpdating(false)
  }

  const handleUseBest = async (index?: number) => {
    try {
      const body = index !== undefined ? { index } : {}
      const r = await client.post('/cookie/pool/use-best', body)
      if (r.data.success) {
        message.success(r.data.message)
        fetchInfo()
      } else {
        message.warning(r.data.message || '应用失败')
      }
    } catch {
      message.error('应用请求失败')
    }
  }

  const handleAdd = async () => {
    if (!newCookies.trim()) {
      message.warning('请输入 Cookie')
      return
    }
    setAddLoading(true)
    try {
      const r = await client.post('/cookie/pool/add', {
        cookies: newCookies.trim(),
        username: newUsername.trim() || '手动添加',
      })
      if (r.data.success) {
        message.success(r.data.message)
        setAddModalOpen(false)
        setNewCookies('')
        setNewUsername('')
        fetchInfo()
      } else {
        message.error(r.data.message || '添加失败')
      }
    } catch {
      message.error('添加请求失败')
    }
    setAddLoading(false)
  }

  const handleRemove = async (index: number) => {
    try {
      const r = await client.post('/cookie/pool/remove', { index })
      if (r.data.success) {
        message.success(r.data.message)
        fetchInfo()
      } else {
        message.error(r.data.message || '删除失败')
      }
    } catch {
      message.error('删除请求失败')
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(
      () => message.success('已复制'),
      () => message.error('复制失败')
    )
  }

  const poolColumns = [
    {
      title: '#',
      dataIndex: 'index',
      width: 60,
      render: (v: number) => <Tag>{v}</Tag>,
    },
    {
      title: 'a1',
      dataIndex: 'a1',
      ellipsis: true,
      render: (v: string) => (
        <Space>
          <Text code style={{ maxWidth: 200 }} ellipsis>{v || '(空)'}</Text>
          {v && (
            <Tooltip title="复制">
              <Button type="text" size="small" icon={<CopyOutlined />}
                onClick={() => copyToClipboard(v)} />
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: '来源',
      dataIndex: 'username',
      width: 120,
    },
    {
      title: '状态',
      dataIndex: 'is_valid',
      width: 80,
      render: (v: boolean) => (
        v ? <Tag color="green" icon={<CheckCircleOutlined />}>有效</Tag>
          : <Tag color="red" icon={<CloseCircleOutlined />}>无效</Tag>
      ),
    },
    {
      title: '操作',
      width: 160,
      render: (_: any, record: CookieItem) => (
        <Space>
          <Button size="small" type="primary"
            onClick={() => handleUseBest(record.index)}>
            应用
          </Button>
          <Popconfirm title="确定移除此 Cookie？"
            onConfirm={() => handleRemove(record.index)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Title level={4}>Cookie 池管理</Title>
      <Paragraph type="secondary">
        管理小红书 Cookie 池，支持批量验证、自动续期、一键应用最佳 Cookie。
      </Paragraph>

      {/* 概览卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic title="池中总数" value={info?.total ?? '-'} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="有效数量" value={info?.valid ?? '-'}
              valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="当前 a1"
              value={info?.active_cookie?.a1 ? '已设置' : '未设置'}
              valueStyle={{ color: info?.active_cookie?.a1 ? '#1890ff' : '#ff4d4f' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="当前状态"
              value={info?.active_cookie?.is_active ? '活跃' : '未激活'}
              valueStyle={{ color: info?.active_cookie?.is_active ? '#52c41a' : '#faad14' }} />
          </Card>
        </Col>
      </Row>

      {/* 当前活跃 Cookie */}
      {info?.active_cookie?.a1 && (
        <Alert
          style={{ marginBottom: 16 }}
          type="info"
          showIcon
          message="当前活跃 Cookie"
          description={
            <Space>
              <Text code style={{ maxWidth: 400 }} ellipsis>
                a1: {info.active_cookie.a1}
              </Text>
              <Button size="small" icon={<CopyOutlined />}
                onClick={() => copyToClipboard(info.active_cookie.a1)}>
                复制
              </Button>
            </Space>
          }
        />
      )}

      {/* 操作栏 */}
      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={fetchInfo}>刷新</Button>
          <Button icon={<SafetyCertificateOutlined />}
            loading={validating} onClick={handleValidateAll}>
            全部验证
          </Button>
          <Button icon={<SyncOutlined />}
            loading={autoUpdating} onClick={handleAutoUpdate}>
            自动续期
          </Button>
          <Button type="primary" icon={<ThunderboltOutlined />}
            onClick={() => handleUseBest()}>
            应用最佳 Cookie
          </Button>
          <Button icon={<PlusOutlined />}
            onClick={() => setAddModalOpen(true)}>
            添加 Cookie
          </Button>
        </Space>
      </Card>

      {/* Cookie 列表 */}
      <Card>
        <Table
          dataSource={info?.pool || []}
          columns={poolColumns}
          rowKey="index"
          loading={loading}
          pagination={false}
          size="small"
          locale={{ emptyText: 'Cookie 池为空，请添加 Cookie' }}
        />
      </Card>

      {/* 添加 Cookie 弹窗 */}
      <Modal
        title="添加 Cookie"
        open={addModalOpen}
        onCancel={() => { setAddModalOpen(false); setNewCookies(''); setNewUsername('') }}
        onOk={handleAdd}
        confirmLoading={addLoading}
        okText="添加"
        width={600}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text strong>Cookie 字符串</Text>
            <TextArea
              rows={4}
              placeholder="粘贴完整的小红书 Cookie 字符串..."
              value={newCookies}
              onChange={e => setNewCookies(e.target.value)}
              style={{ marginTop: 8 }}
            />
          </div>
          <div>
            <Text strong>备注（可选）</Text>
            <Input
              placeholder="如：账号名称、来源等"
              value={newUsername}
              onChange={e => setNewUsername(e.target.value)}
              style={{ marginTop: 8 }}
            />
          </div>
        </Space>
      </Modal>
    </div>
  )
}
