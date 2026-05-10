import React, { useEffect, useState } from 'react'
import { Card, Form, Input, Button, Switch, Space, Typography, Row, Col, Divider, message, Tag } from 'antd'
import { ReloadOutlined, CheckCircleOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text } = Typography

export default function AntiCrawlPage() {
  const [config, setConfig] = useState<any>({})
  const [loading, setLoading] = useState(false)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const r = await client.get('/anti-crawl/config')
      setConfig(r.data)
      form.setFieldsValue({
        min_delay: r.data.rate_limiter?.min_delay,
        max_delay: r.data.rate_limiter?.max_delay,
        proxy_enabled: r.data.proxy_pool?.enabled,
      })
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const onSave = async (values: any) => {
    await client.post('/anti-crawl/config', {
      rate_limiter: { min_delay: values.min_delay, max_delay: values.max_delay },
      proxy_pool: { enabled: values.proxy_enabled },
    })
    message.success('配置已保存')
    load()
  }

  const onRegenFingerprint = async () => {
    const r = await client.post('/anti-crawl/fingerprint')
    message.success('指纹已重新生成')
    load()
  }

  const onCheckProxy = async () => {
    const r = await client.post('/anti-crawl/proxy/check')
    message.success('代理健康检查完成')
  }

  return (
    <div>
      <Title level={4}>反爬配置</Title>
      <Row gutter={16}>
        <Col span={12}>
          <Card title="频率控制" size="small" loading={loading}>
            <Form form={form} onFinish={onSave} layout="vertical">
              <Form.Item name="min_delay" label="最小延迟(秒)">
                <Input type="number" />
              </Form.Item>
              <Form.Item name="max_delay" label="最大延迟(秒)">
                <Input type="number" />
              </Form.Item>
              <Form.Item name="proxy_enabled" label="启用代理" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Button type="primary" htmlType="submit">保存配置</Button>
            </Form>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="浏览器指纹" size="small" loading={loading}>
            <div style={{ marginBottom: 16 }}>
              <Text strong>当前指纹：</Text>
              <pre style={{ fontSize: 12, maxHeight: 200, overflow: 'auto', background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
                {JSON.stringify(config.fingerprint || {}, null, 2)}
              </pre>
            </div>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={onRegenFingerprint}>重新生成指纹</Button>
              <Button icon={<CheckCircleOutlined />} onClick={onCheckProxy}>代理健康检查</Button>
            </Space>
          </Card>
          <Card title="请求统计" size="small" style={{ marginTop: 16 }} loading={loading}>
            <pre style={{ fontSize: 12, maxHeight: 150, overflow: 'auto', background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
              {JSON.stringify(config.rate_limiter || {}, null, 2)}
            </pre>
          </Card>
          <Card title="代理池状态" size="small" style={{ marginTop: 16 }} loading={loading}>
            <pre style={{ fontSize: 12, maxHeight: 150, overflow: 'auto', background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
              {JSON.stringify(config.proxy_pool || {}, null, 2)}
            </pre>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
