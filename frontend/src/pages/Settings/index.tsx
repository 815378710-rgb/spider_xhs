import React, { useEffect, useState } from 'react'
import { Card, Form, Input, Button, Select, Space, Typography, Tabs, message, Divider } from 'antd'
import { SaveOutlined, ThunderboltOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text } = Typography

export default function SettingsPage() {
  const [form] = Form.useForm()
  const [aiForm] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [aiTesting, setAiTesting] = useState(false)
  const [models, setModels] = useState<any[]>([])

  const load = async () => {
    try {
      const r = await client.get('/config')
      const d = r.data
      form.setFieldsValue({ cookies: d.cookies })
      aiForm.setFieldsValue({
        llm_provider: d.llm_provider, llm_api_key: d.llm_api_key,
        llm_model: d.llm_model, llm_base_url: d.llm_base_url,
      })
    } catch {}
  }

  useEffect(() => { load() }, [])

  const onSaveCookie = async (values: any) => {
    setLoading(true)
    await client.post('/config', values)
    message.success('Cookie已保存')
    setLoading(false)
  }

  const onTestCookie = async () => {
    const r = await client.post('/config/test-cookie')
    if (r.data.success) message.success(r.data.message)
    else message.warning(r.data.message)
  }

  const onSaveAI = async (values: any) => {
    setLoading(true)
    await client.post('/config', values)
    message.success('AI配置已保存')
    setLoading(false)
  }

  const onTestAI = async () => {
    setAiTesting(true)
    try {
      const values = aiForm.getFieldsValue()
      const r = await client.post('/config/test-ai', values)
      if (r.data.success) message.success(r.data.message)
      else message.warning(r.data.message)
    } catch {}
    setAiTesting(false)
  }

  const onLoadModels = async () => {
    try {
      const values = aiForm.getFieldsValue()
      const r = await client.post('/config/models', values)
      if (r.data.success) {
        setModels(r.data.models || [])
        message.success(`获取到 ${r.data.models?.length || 0} 个模型`)
      }
    } catch {}
  }

  return (
    <div>
      <Title level={4}>系统设置</Title>
      <Tabs items={[
        {
          key: 'cookie',
          label: 'Cookie配置',
          children: (
            <Card>
              <Form form={form} onFinish={onSaveCookie} layout="vertical">
                <Form.Item name="cookies" label="小红书 Cookie">
                  <Input.TextArea rows={8} placeholder="粘贴完整的Cookie字符串..." />
                </Form.Item>
                <Space>
                  <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={loading}>保存</Button>
                  <Button onClick={onTestCookie}>测试有效性</Button>
                </Space>
              </Form>
            </Card>
          ),
        },
        {
          key: 'ai',
          label: 'AI模型配置',
          children: (
            <Card>
              <Form form={aiForm} onFinish={onSaveAI} layout="vertical">
                <Form.Item name="llm_provider" label="AI服务商" initialValue="deepseek">
                  <Select options={[
                    { value: 'deepseek', label: 'DeepSeek' },
                    { value: 'mimo', label: '小米MiMo' },
                    { value: 'openai', label: 'OpenAI兼容' },
                  ]} />
                </Form.Item>
                <Form.Item name="llm_api_key" label="API Key">
                  <Input.Password placeholder="sk-..." />
                </Form.Item>
                <Form.Item name="llm_model" label="模型名称" initialValue="deepseek-v3">
                  <Select showSearch options={models.map(m => ({ value: m.id, label: m.name || m.id }))}
                    placeholder="输入后点获取模型列表" />
                </Form.Item>
                <Form.Item name="llm_base_url" label="Base URL（可选）">
                  <Input placeholder="留空使用默认地址" />
                </Form.Item>
                <Space>
                  <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={loading}>保存</Button>
                  <Button icon={<ThunderboltOutlined />} loading={aiTesting} onClick={onTestAI}>测试连接</Button>
                  <Button onClick={onLoadModels}>获取模型列表</Button>
                </Space>
              </Form>
            </Card>
          ),
        },
        {
          key: 'about',
          label: '关于',
          children: (
            <Card>
              <Typography>
                <Title level={5}>🥔 土豆小红书助手 v2.0</Title>
                <Divider />
                <p><strong>技术栈：</strong>FastAPI + React 19 + Ant Design 6 + SQLite</p>
                <p><strong>功能：</strong>笔记采集 · AI改写 · 图片防重 · 多账号管理 · 定时发布 · 全自动流水线 · 竞品监控</p>
                <p><strong>签名引擎：</strong>12个JS签名文件 + PyExecJS</p>
                <p><strong>部署：</strong>Docker on NAS (port 5000)</p>
                <Text type="secondary">Built with ❤️ by 老大 + 猫猫侠</Text>
              </Typography>
            </Card>
          ),
        },
      ]} />
    </div>
  )
}
