import React, { useEffect, useState, useCallback } from 'react'
import { Card, Input, Button, Switch, Space, Typography, Row, Col, Statistic, Tag, Progress, Table, message, Tooltip, Divider, Form, Badge, Alert } from 'antd'
import { ReloadOutlined, CheckCircleOutlined, ExclamationCircleOutlined, SafetyOutlined, BugOutlined, ApiOutlined, ExperimentOutlined, ThunderboltOutlined, SyncOutlined, ClockCircleOutlined, LockOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text } = Typography

export default function AntiCrawlPage() {
  const [status, setStatus] = useState<any>({})
  const [loading, setLoading] = useState(false)
  const [testApi, setTestApi] = useState('/api/sns/web/v1/user/self')
  const [testResult, setTestResult] = useState<any>(null)
  const [testLoading, setTestLoading] = useState(false)
  const [a1RefreshLoading, setA1RefreshLoading] = useState(false)
  const [tlsStatus, setTlsStatus] = useState<any>({})

  const loadStatus = useCallback(async () => {
    try {
      const [statusRes, tlsRes] = await Promise.all([
        client.get('/crawl-monitor/status'),
        client.get('/crawl-monitor/tls-status').catch(() => ({ data: { success: false } })),
      ])
      if (statusRes.data.success) setStatus(statusRes.data.data)
      if (tlsRes.data.success) setTlsStatus(tlsRes.data.data)
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

  const onA1Refresh = async () => {
    setA1RefreshLoading(true)
    try {
      const r = await client.post('/crawl-monitor/a1-refresh')
      if (r.data.data?.success) {
        message.success('a1续期成功')
      } else {
        message.warning('a1续期失败: ' + (r.data.data?.message || '未知错误'))
      }
      loadStatus()
    } catch (e: any) {
      message.error('续期失败: ' + (e.response?.data?.message || e.message))
    }
    setA1RefreshLoading(false)
  }

  const rl = status.rate_limiter || {}
  const health = status.health || {}
  const cookie = status.cookie || {}
  const fp = status.fingerprint || {}
  const proxy = status.proxy_pool || {}
  const a1 = status.a1_refresh || {}

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <Title level={4}><SafetyOutlined /> 反爬管理 <Text type="secondary" style={{ fontSize: 14 }}>v2.1.0</Text></Title>
      <div style={{ marginBottom: 16, padding: 12, background: '#f6f8fa', borderRadius: 8, border: '1px solid #e8e8e8' }}>
        <Text type="secondary">
          💡 反爬管理帮助你维护与小红书服务器的稳定连接。系统会自动管理请求频率、Cookie有效性、a1自动续期和TLS指纹伪装，
          防止因频繁请求被封禁。如遇到"采集失败"或"请求被拒"等问题，可在此检查各项状态。
        </Text>
      </div>

      {/* ── 第一行：核心安全状态 ── */}
      <Row gutter={[16, 16]}>
        {/* 1. Cookie管理 + a1自动续期 */}
        <Col span={12}>
          <Card title="🔐 Cookie管理 & a1续期" size="small" extra={
            <Tag color={cookie.has_cookie ? 'green' : 'red'}>
              {cookie.has_cookie ? '已配置' : '未配置'}
            </Tag>
          }>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>a1有效期仅10分钟，系统每8分钟自动续期</Text>

              {/* a1续期状态区域 */}
              <div style={{ padding: 8, background: '#f0f5ff', borderRadius: 6, border: '1px solid #d6e4ff' }}>
                <Row gutter={12}>
                  <Col span={12}>
                    <Statistic
                      title="a1续期次数"
                      value={a1.refresh_count || 0}
                      prefix={<SyncOutlined spin={a1.is_refreshing} />}
                      valueStyle={{ fontSize: 16 }}
                    />
                  </Col>
                  <Col span={12}>
                    <Statistic
                      title="成功率"
                      value={a1.success_rate != null ? `${(a1.success_rate * 100).toFixed(0)}%` : '--'}
                      valueStyle={{ fontSize: 16, color: a1.consecutive_failures > 0 ? '#ff4d4f' : '#52c41a' }}
                    />
                  </Col>
                </Row>
                {a1.last_refresh && (
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    <ClockCircleOutlined /> 上次续期: {a1.last_refresh}
                  </Text>
                )}
                {a1.current_a1 && (
                  <div style={{ marginTop: 4 }}>
                    <Text type="secondary" style={{ fontSize: 11 }}>当前a1: </Text>
                    <Tag color="blue" style={{ fontSize: 11, fontFamily: 'monospace' }}>{a1.current_a1}</Tag>
                  </div>
                )}
                {a1.consecutive_failures > 0 && (
                  <Alert
                    type="error"
                    message={`连续失败${a1.consecutive_failures}次: ${a1.last_error}`}
                    style={{ marginTop: 8, fontSize: 12 }}
                    showIcon
                    banner
                  />
                )}
              </div>

              <Statistic title="a1值（Cookie核心标识）" value={cookie.a1 || '未获取'} valueStyle={{ fontSize: 14 }} />
              <Space>
                <Button type="primary" icon={<CheckCircleOutlined />} onClick={onHealthCheck} loading={loading}>
                  检测Cookie有效性
                </Button>
                <Button icon={<SyncOutlined />} onClick={onA1Refresh} loading={a1RefreshLoading}>
                  手动续期a1
                </Button>
              </Space>
            </Space>
          </Card>
        </Col>

        {/* 2. 系统健康 + TLS指纹 */}
        <Col span={12}>
          <Card title="🏥 系统健康" size="small" extra={
            health.consecutive_failures > 0
              ? <Tag color="red">连续失败{health.consecutive_failures}次</Tag>
              : <Tag color="green">正常</Tag>
          }>
            <Row gutter={16}>
              <Col span={8}>
                <Statistic title="签名成功率" value={health.sign_success_rate != null ? `${(health.sign_success_rate * 100).toFixed(1)}%` : '--'} />
              </Col>
              <Col span={8}>
                <Statistic title="巡检次数" value={health.check_count || 0} />
              </Col>
              <Col span={8}>
                <Statistic title="签名总量" value={health.sign_total || 0} />
              </Col>
            </Row>
            <Divider style={{ margin: '12px 0' }} />
            {/* TLS指纹状态 */}
            <div style={{ padding: 8, background: '#f6ffed', borderRadius: 6, border: '1px solid #b7eb8f' }}>
              <Row gutter={12} align="middle">
                <Col span={8}>
                  <Space direction="vertical" size={0}>
                    <Text type="secondary" style={{ fontSize: 11 }}>TLS指纹模拟</Text>
                    <Tag color={tlsStatus.curl_cffi_available ? 'green' : 'orange'} icon={<LockOutlined />} style={{ marginTop: 2 }}>
                      {tlsStatus.curl_cffi_available ? '已启用' : '未安装'}
                    </Tag>
                  </Space>
                </Col>
                <Col span={8}>
                  <Space direction="vertical" size={0}>
                    <Text type="secondary" style={{ fontSize: 11 }}>模拟目标</Text>
                    <Text style={{ fontSize: 12, fontFamily: 'monospace' }}>{tlsStatus.impersonate_target || '--'}</Text>
                  </Space>
                </Col>
                <Col span={8}>
                  <Space direction="vertical" size={0}>
                    <Text type="secondary" style={{ fontSize: 11 }}>版本</Text>
                    <Text style={{ fontSize: 12 }}>{tlsStatus.curl_cffi_version || '--'}</Text>
                  </Space>
                </Col>
              </Row>
            </div>
          </Card>
        </Col>

        {/* 3. 频率控制 */}
        <Col span={12}>
          <Card title="⏱️ 频率控制" size="small" extra={
            <Tooltip title="系统自动控制请求频率，避免因过于频繁的请求被小红书识别为爬虫">
              <Text type="secondary" style={{ fontSize: 12 }}>自动控制，防封号</Text>
            </Tooltip>
          }>
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
          <Card title="🌐 代理池" size="small" extra={
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
          <Card title="🧑‍💻 浏览器指纹" size="small" extra={
            <Space>
              <Tooltip title="浏览器指纹用于模拟真实浏览器环境，让请求看起来像真人操作">
                <Text type="secondary" style={{ fontSize: 12 }}>防识别</Text>
              </Tooltip>
              <Button size="small" icon={<ThunderboltOutlined />} onClick={onRegenFingerprint}>重新生成</Button>
            </Space>
          }>
            <Row gutter={[8, 8]}>
              {Object.entries(fp).length === 0 && <Text type="secondary">暂无指纹数据</Text>}
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
