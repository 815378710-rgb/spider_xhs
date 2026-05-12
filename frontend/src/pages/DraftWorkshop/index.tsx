import React, { useEffect, useState } from 'react'
import { Card, Table, Button, Space, Typography, Modal, Form, Input, message, Popconfirm, Row, Col } from 'antd'
import { PlusOutlined, DeleteOutlined, SendOutlined, RobotOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text } = Typography

export default function DraftWorkshopPage() {
  const [drafts, setDrafts] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState<any>(null)
  const [form] = Form.useForm()
  const [rewriteLoading, setRewriteLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const r = await client.get('/drafts', { params: { page } })
      setDrafts(r.data.data || [])
      setTotal(r.data.total || 0)
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [page])

  const onCreate = async (values: any) => {
    try {
      await client.post('/drafts', values)
      message.success('草稿已创建')
      form.resetFields()
      load()
    } catch (e: any) {
      message.error('创建草稿失败: ' + (e.response?.data?.detail || e.response?.data?.message || e.message || '未知错误'))
    }
  }

  const onUpdate = async () => {
    if (!editing) return
    try {
      const values = form.getFieldsValue()
      await client.put(`/drafts/${editing.id}`, values)
      message.success('已更新')
      setEditing(null)
      load()
    } catch (e: any) {
      message.error('更新失败: ' + (e.response?.data?.detail || e.response?.data?.message || e.message || '未知错误'))
    }
  }

  const onDelete = async (id: number) => {
    try {
      await client.delete(`/drafts/${id}`)
      message.success('已删除')
      load()
    } catch (e: any) {
      message.error('删除失败: ' + (e.response?.data?.detail || e.response?.data?.message || e.message || '未知错误'))
    }
  }

  const onAIRewrite = async (draft: any) => {
    setRewriteLoading(true)
    try {
      const r = await client.post('/note/rewrite', {
        title: draft.title, desc: draft.content, style: '小红书爆款', rewrite_ratio: 60,
      })
      if (r.data.success) {
        form.setFieldsValue({ title: r.data.data.title, content: r.data.data.desc })
        message.success('AI改写完成')
      } else {
        message.error(r.data.message)
      }
    } catch (e: any) {
      message.error('改写失败')
    }
    setRewriteLoading(false)
  }

  const onPublish = async (draft: any) => {
    try {
      await client.post('/publish', {
        title: draft.title, content: draft.content,
        images_json: draft.images_json, tags_json: draft.tags_json,
      })
      message.success('已提交发布')
    } catch (e: any) {
      message.error('发布失败: ' + (e.response?.data?.detail || e.response?.data?.message || e.message || '未知错误'))
    }
  }

  return (
    <div>
      <Title level={4}>草稿工作台</Title>
      <Row gutter={16}>
        {/* Draft list */}
        <Col span={8}>
          <Card title="草稿列表" size="small" extra={<Button size="small" icon={<PlusOutlined />}
            onClick={() => { setEditing(null); form.resetFields() }}>新建</Button>}>
            <Table dataSource={drafts} rowKey="id" loading={loading} size="small" pagination={{ total, current: page, onChange: setPage, pageSize: 10 }}
              columns={[
                { title: '标题', dataIndex: 'title', ellipsis: true },
                { title: '操作', width: 80, render: (_: any, r: any) => (
                  <Space>
                    <Button size="small" type="link" onClick={() => { setEditing(r); form.setFieldsValue(r) }}>编辑</Button>
                    <Popconfirm title="删除？" onConfirm={() => onDelete(r.id)}>
                      <Button size="small" type="link" danger>删</Button>
                    </Popconfirm>
                  </Space>
                )},
              ]} />
          </Card>
        </Col>

        {/* Editor */}
        <Col span={16}>
          <Card title={editing ? `编辑: ${editing.title}` : '新建草稿'} size="small">
            <Form form={form} onFinish={editing ? onUpdate : onCreate} layout="vertical">
              <Form.Item name="title" label="标题" rules={[{ required: true }]}>
                <Input placeholder="笔记标题" />
              </Form.Item>
              <Form.Item name="content" label="正文">
                <Input.TextArea rows={12} placeholder="笔记正文内容..." />
              </Form.Item>
              <Form.Item name="tags_json" label="标签（JSON数组）">
                <Input placeholder='["标签1", "标签2"]' />
              </Form.Item>
              <Space>
                <Button type="primary" htmlType="submit">{editing ? '更新' : '创建'}</Button>
                <Button icon={<RobotOutlined />} loading={rewriteLoading}
                  onClick={() => onAIRewrite(form.getFieldsValue())}>AI改写</Button>
                {editing && <Button icon={<SendOutlined />} type="primary" ghost
                  onClick={() => onPublish(editing)}>发布</Button>}
              </Space>
            </Form>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
