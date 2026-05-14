import React, { useState, useEffect } from 'react'
import { App,  Card, Typography, Table, Input, Button, Space, Select, Tag, Modal, Descriptions, Spin } from 'antd'
import { SearchOutlined, UserOutlined, ReloadOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text, Paragraph } = Typography

interface Distributor {
  user_id: string
  nickname: string
  avatar: string
  followers: number
  category: string
  [key: string]: any
}

export default function QianFanPage() {
  const [categories, setCategories] = useState<any[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [distributors, setDistributors] = useState<Distributor[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [detailModal, setDetailModal] = useState(false)
  const [currentDetail, setCurrentDetail] = useState<any>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // Load categories on mount
  useEffect(() => {
    loadCategories()
  }, [])

  const loadCategories = async () => {
    try {
      const r = await client.get('/qianfan/categories')
      if (r.data.success && Array.isArray(r.data.data)) {
        setCategories(r.data.data)
        if (r.data.data.length > 0) {
          setSelectedCategory(r.data.data[0])
        }
      }
    } catch (e: any) {
      message.error('获取分类失败：' + (e.response?.data?.message || e.message))
    }
  }

  const searchDistributors = async (p = 1) => {
    if (!selectedCategory) {
      message.warning('请先选择分类')
      return
    }
    setLoading(true)
    try {
      const r = await client.post('/qianfan/search', {
        page: p,
        category: selectedCategory,
      })
      if (r.data.success) {
        setDistributors(r.data.data || [])
        setTotal(r.data.total || 0)
        setPage(p)
      } else {
        message.error(r.data.message || '搜索失败')
      }
    } catch (e: any) {
      message.error('搜索失败：' + (e.response?.data?.message || e.message))
    }
    setLoading(false)
  }

  const loadDetail = async (userId: string) => {
    setDetailLoading(true)
    setDetailModal(true)
    try {
      const r = await client.get(`/qianfan/${userId}/detail`)
      if (r.data.success) {
        setCurrentDetail(r.data.data)
      } else {
        message.error(r.data.message || '获取详情失败')
        setDetailModal(false)
      }
    } catch (e: any) {
      message.error('获取详情失败：' + (e.response?.data?.message || e.message))
      setDetailModal(false)
    }
    setDetailLoading(false)
  }

  const columns = [
    {
      title: '达人',
      dataIndex: 'nickname',
      key: 'nickname',
      render: (text: string, record: Distributor) => (
        <Space>
          {record.avatar && (
            <img src={record.avatar} alt="" style={{ width: 32, height: 32, borderRadius: '50%' }} />
          )}
          <a onClick={() => loadDetail(record.user_id)}>{text || '未知'}</a>
        </Space>
      ),
    },
    {
      title: '粉丝数',
      dataIndex: 'followers',
      key: 'followers',
      render: (val: number) => val ? val.toLocaleString() : '-',
      sorter: (a: any, b: any) => (a.followers || 0) - (b.followers || 0),
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      render: (text: string) => text ? <Tag>{text}</Tag> : '-',
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: Distributor) => (
        <Button type="link" size="small" onClick={() => loadDetail(record.user_id)}>
          查看详情
        </Button>
      ),
    },
  ]

  return (
    <div>
      <Title level={4}>千帆分销 - 达人搜索</Title>
      <Paragraph type="secondary">
        通过千帆平台搜索小红书达人，用于分销合作
      </Paragraph>

      <Card style={{ marginBottom: 16 }}>
        <Space size="middle" wrap>
          <div>
            <Text strong>选择分类：</Text>
            <Select
              style={{ width: 300, marginLeft: 8 }}
              value={selectedCategory || undefined}
              onChange={setSelectedCategory}
              placeholder="请选择分类"
              loading={categories.length === 0}
            >
              {categories.map((cat, idx) => (
                <Select.Option key={idx} value={cat}>{cat}</Select.Option>
              ))}
            </Select>
          </div>
          <Button type="primary" icon={<SearchOutlined />} onClick={() => searchDistributors(1)} loading={loading}>
            搜索达人
          </Button>
          <Button icon={<ReloadOutlined />} onClick={loadCategories}>
            刷新分类
          </Button>
        </Space>
      </Card>

      <Card>
        <Table
          columns={columns}
          dataSource={distributors}
          rowKey="user_id"
          loading={loading}
          pagination={{
            current: page,
            total,
            pageSize: 20,
            onChange: (p) => searchDistributors(p),
          }}
        />
      </Card>

      <Modal
        title="达人详情"
        open={detailModal}
        onCancel={() => setDetailModal(false)}
        footer={null}
        width={600}
      >
        {detailLoading ? (
          <Spin />
        ) : currentDetail ? (
          <Descriptions bordered column={1}>
            <Descriptions.Item label="昵称">{currentDetail.nickname || '-'}</Descriptions.Item>
            <Descriptions.Item label="用户ID">{currentDetail.user_id || '-'}</Descriptions.Item>
            <Descriptions.Item label="粉丝数">{currentDetail.followers ? currentDetail.followers.toLocaleString() : '-'}</Descriptions.Item>
            <Descriptions.Item label="简介">{currentDetail.description || '-'}</Descriptions.Item>
            {currentDetail.avatar && (
              <Descriptions.Item label="头像">
                <img src={currentDetail.avatar} alt="" style={{ width: 64, height: 64, borderRadius: '50%' }} />
              </Descriptions.Item>
            )}
          </Descriptions>
        ) : (
          <Text type="secondary">暂无数据</Text>
        )}
      </Modal>
    </div>
  )
}
