import React, { useEffect, useState, useCallback } from 'react'
import { Card, Input, Button, Switch, Space, Typography, Row, Col, Statistic, Tag, Progress, Table, message, Tooltip, Divider, Form } from 'antd'
import { ReloadOutlined, CheckCircleOutlined, ExclamationCircleOutlined, SafetyOutlined, BugOutlined, ApiOutlined, ExperimentOutlined, ThunderboltOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text } = Typography

export default function AntiCrawlPage() {
  const [status, setStatus] = useState<any>({})
  const [loading, setLoading] = useState(false)
  const [testApi, setTestApi] = useState('/api/sns/web/v1/user/self')
  const [testResult, setTestResult] = useState<any>(null)
  const [testLoading, setTestLoading] = useState(false)

  const loadStatus = useCallback(async () => {
    try {
      const r = await client.get('/crawl-monitor/status')
      if (r.data.success) setStatus(r.data.data)
    } catch {}
  }, [])

  useEffect(() => {
    loadStatus()
    const timer = setInterval(loadStatus, 10000)
    return () => clearInterval(timer)
  }, [loadStatus])

  const onHealthCheck = async () => {
    setLoading(true)
    try {
      const r = await client.post('/crawl-monitor/health-check')
      message.success(r.data.data?.valid ? 'Cookie有效' : 'Cookie已过期')
      loadStatus()
    } catch (e: any) {
      message.error('检查失败: ' + (e.response?.data?.message || e.message))
    }
    setLoading(false)
  }

  const onTestRequest = async () => {
    setTestLoading(true)
    try {
      const r = await client.post('/crawl-monitor/test-request', { api: testApi })
      setTestResult(r.data.data)
    } catch (e: any) {
      setTestResult({ error: e.message })
    }
    setTestLoading(false)
  }

  const onRegenFingerprint = async () => {
    try {
      await client.post('/anti-crawl/fingerprint')
      message.success('指纹已重新生成')
      loadStatus()
    } catch { message.error('生成失败') }
  }

  const onCheckProxy = async () => {
    try {
      await client.post('/anti-crawl/proxy/check')
      message.success('代理健康检查完成')
      loadStatus()
    } catch { message.error('检查失败') }
  }

  const rl = status.rate_limiter || {}
  const health = status.health || {}
  const cookie = status.cookie || {}
  const fp = status.fingerprint || {}
  const proxy = status.proxy_pool || {}

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <Title level={4}><SafetyOutlined /> 反爬管理</Title>

      <Row gutter={[16, 16]}>
        {/* 1. Cookie管理 */}
        <Col span={12}>
          <Card title="Cookie管理" size="small" extra={
            <Tag color={cookie.has_cookie ? 'green' : 'red'}>
              {cookie.has_cookie ? '已配置' : '未配置'}
            </Tag>
          }>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Statistic title="a1值" value={cookie.a1 || '未获取'} valueStyle={{ fontSize: 14 }} />
              <Button type="primary" icon={<CheckCircleOutlined />} onClick={onHealthCheck} loading={loading}>
                检测Cookie有效性
              </Button>
            </Space>
          </Card>
        </Col>

        {/* 2. 系统健康 */}
        <Col span={12}>
          <Card title="系统健康" size="small" extra={
            health.consecutive_failures > 0
              ? <Tag color="red">连续失败{health.consecutive_failures}次</Tag>
              : <Tag color="green">正常</Tag>
          }>
            <Row gutter={16}>
              <Col span={12}>
                <Statistic title="签名成功率" value={health.sign_success_rate != null ? `${(health.sign_success_rate * 100).toFixed(1)}%` : '--'} />
              </Col>
              <Col span={12}>
                <Statistic title="巡检次数" value={health.check_count || 0} />
              </Col>
            </Row>
          </Card>
        </Col>

        {/* 3. 频率控制 */}
        <Col span={12}>
          <Card title="频率控制" size="small">
            <Row gutter={16}>
              <Col span={8}>
                <Statistic title="总请求" value={rl.total_requests || 0} />
              </Col>
              <Col span={8}>
                <Statistic title="今日请求" value={rl.daily_count || 0} suffix={`/${rl.max_per_day || 100}`} />
              </Col>
              <Col span={8}>
                <Statistic title="分钟内" value={rl.minute_requests || 0} suffix={`/${rl.max_per_minute || 5}`} />
              </Col>
            </Row>
            <Divider style={{ margin: '12px 0' }} />
            <Row gutter={16}>
              <Col span={8}>
                <Statistic title="延时范围" value={`${rl.min_delay || 5}-${rl.max_delay || 15}s`} valueStyle={{ fontSize: 14 }} />
              </Col>
              <Col span={8}>
                <Statistic title="平均延时" value={rl.avg_delay ? `${rl.avg_delay.toFixed(1)}s` : '--'} valueStyle={{ fontSize: 14 }} />
              </Col>
              <Col span={8}>
                <Statistic title="连续请求" value={`${rl.consecutive_count || 0}/${rl.max_consecutive || 10}`} valueStyle={{ fontSize: 14 }} />
              </Col>
            </Row>
          </Card>
        </Col>

        {/* 4. 代理池 */}
        <Col span={12}>
          <Card title="代理池" size="small" extra={
            <Space>
              <Tag color={proxy.enabled ? 'green' : 'default'}>{proxy.enabled ? '已启用' : '已禁用'}</Tag>
              <Button size="small" icon={<ReloadOutlined />} onClick={onCheckProxy}>健康检查</Button>
            </Space>
          }>
            <Row gutter={16}>
              <Col span={8}>
                <Statistic title="总数" value={proxy.total || 0} />
              </Col>
              <Col span={8}>
                <Statistic title="健康" value={proxy.healthy || 0} valueStyle={{ color: '#52c41a' }} />
              </Col>
              <Col span={8}>
                <Statistic title="不健康" value={proxy.unhealthy || 0} valueStyle={{ color: '#ff4d4f' }} />
              </Col>
            </Row>
            {proxy.proxies && proxy.proxies.length > 0 && (
              <div style={{ marginTop: 8, maxHeight: 100, overflowY: 'auto' }}>
                {proxy.proxies.map((p: any, i: number) => (
                  <div key={i} style={{ fontSize: 12, padding: '2px 0' }}>
                    <Tag color={p.ok ? 'green' : 'red'} style={{ marginRight: 4 }}>{p.ok ? 'OK' : 'DOWN'}</Tag>
                    <Text type="secondary">{p.url}</Text>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </Col>

        {/* 5. 浏览器指纹 */}
        <Col span={12}>
          <Card title="浏览器指纹" size="small" extra={
            <Button size="small" icon={<ThunderboltOutlined />} onClick={onRegenFingerprint}>重新生成</Button>
          }>
            <Row gutter={[8, 8]}>
              {Object.entries(fp).map(([k, v]) => (
                <Col span={12} key={k}>
                  <Text type="secondary" style={{ fontSize: 12 }}>{k}: </Text>
                  <Text style={{ fontSize: 12 }}>{String(v)}</Text>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>

        {/* 6. 测试工具 */}
        <Col span={12}>
          <Card title="测试工具" size="small" extra={<ExperimentOutlined />}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Input
                placeholder="API路径"
                value={testApi}
                onChange={e => setTestApi(e.target.value)}
                addonBefore="GET"
              />
              <Button type="primary" icon={<ApiOutlined />} onClick={onTestRequest} loading={testLoading}>
                发送测试请求
              </Button>
              {testResult && (
                <pre style={{
                  fontSize: 11, maxHeight: 150, overflow: 'auto',
                  background: '#1e1e1e', color: '#d4d4d4', padding: 8, borderRadius: 4,
                }}>
                  {JSON.stringify(testResult, null, 2)}
                </pre>
              )}
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
