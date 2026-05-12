import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Card, Typography, Space, Button, Tag, Select, Badge, Switch, Empty, Alert, Spin } from 'antd'
import { PauseCircleOutlined, PlayCircleOutlined, ClearOutlined, ReloadOutlined, WifiOutlined, DisconnectOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text } = Typography

interface LogEntry {
  id: number
  level: string
  message: string
  time: string
  module: string
  function: string
}

const LEVEL_COLORS: Record<string, string> = {
  INFO: 'blue',
  WARNING: 'orange',
  ERROR: 'red',
  SUCCESS: 'green',
  DEBUG: 'default',
}

const LEVEL_BG: Record<string, string> = {
  INFO: '#e6f7ff',
  WARNING: '#fff7e6',
  ERROR: '#fff1f0',
  SUCCESS: '#f6ffed',
  DEBUG: '#f5f5f5',
}

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [paused, setPaused] = useState(false)
  const [levelFilter, setLevelFilter] = useState<string>('')
  const [connected, setConnected] = useState(false)
  const [usingFallback, setUsingFallback] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>('')
  const containerRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)
  const pollRef = useRef<any>(null)
  const autoScrollRef = useRef(true)
  const logIdSetRef = useRef(new Set<number>())

  // Load initial history via HTTP
  const loadHistory = async () => {
    setLoading(true)
    try {
      const r = await client.get('/logs', { params: { page: 1, page_size: 100 } })
      if (r.data.success && r.data.data) {
        const entries = r.data.data as LogEntry[]
        setLogs(entries)
        entries.forEach(e => logIdSetRef.current.add(e.id))
      }
    } catch (e: any) {
      setError('加载日志失败: ' + (e.message || '未知错误'))
    }
    setLoading(false)
  }

  // HTTP polling fallback
  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current)
    setUsingFallback(true)
    pollRef.current = setInterval(async () => {
      try {
        const r = await client.get('/logs', { params: { page: 1, page_size: 50 } })
        if (r.data.success && r.data.data) {
          const entries = r.data.data as LogEntry[]
          const newEntries = entries.filter(e => !logIdSetRef.current.has(e.id))
          if (newEntries.length > 0) {
            setLogs(prev => {
              const next = [...newEntries, ...prev]
              return next.slice(0, 500)
            })
            newEntries.forEach(e => logIdSetRef.current.add(e.id))
          }
        }
      } catch {}
    }, 3000)
  }, [])

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
    setUsingFallback(false)
  }, [])

  // Try SSE first, fallback to polling
  const connectSSE = useCallback(() => {
    if (esRef.current) esRef.current.close()
    stopPolling()
    setError('')

    try {
      const es = new EventSource('/api/logs/stream')
      esRef.current = es

      es.onopen = () => {
        setConnected(true)
        setUsingFallback(false)
        setError('')
      }

      es.onerror = () => {
        setConnected(false)
        es.close()
        // Fallback to HTTP polling
        startPolling()
      }

      es.onmessage = (e) => {
        if (paused) return
        try {
          const entry = JSON.parse(e.data)
          if (!logIdSetRef.current.has(entry.id)) {
            logIdSetRef.current.add(entry.id)
            setLogs(prev => {
              const next = [entry, ...prev]
              return next.slice(0, 500)
            })
          }
        } catch {}
      }
    } catch {
      // SSE not supported or connection error, use polling
      setConnected(false)
      startPolling()
    }
  }, [paused, startPolling, stopPolling])

  // Initial load + SSE connection
  useEffect(() => {
    loadHistory().then(() => connectSSE())
    return () => {
      esRef.current?.close()
      stopPolling()
    }
  }, [])

  // Reconnect when paused changes
  useEffect(() => {
    if (!paused) {
      connectSSE()
    } else {
      esRef.current?.close()
      stopPolling()
    }
  }, [paused])

  useEffect(() => {
    if (autoScrollRef.current && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [logs])

  const filteredLogs = levelFilter
    ? logs.filter(l => l.level === levelFilter)
    : logs

  const connectionStatus = connected
    ? { color: 'success', text: 'SSE实时连接', icon: <WifiOutlined /> }
    : usingFallback
    ? { color: 'warning', text: 'HTTP轮询模式', icon: <ReloadOutlined /> }
    : { color: 'error', text: '未连接', icon: <DisconnectOutlined /> }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <Title level={4}>运行日志</Title>

      {error && (
        <Alert type="warning" message={error} closable style={{ marginBottom: 16 }}
          action={<Button size="small" onClick={connectSSE}>重试</Button>} />
      )}

      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <Space wrap>
            <Badge status={connectionStatus.color as any} text={
              <Space>
                {connectionStatus.icon}
                <span>{connectionStatus.text}</span>
              </Space>
            } />
            <Tag>共 {logs.length} 条</Tag>
          </Space>
          <Space wrap>
            <Select
              placeholder="按级别过滤"
              allowClear
              style={{ width: 150 }}
              value={levelFilter || undefined}
              onChange={v => setLevelFilter(v || '')}
              options={Object.keys(LEVEL_COLORS).map(l => ({ label: l, value: l }))}
            />
            <Switch
              checked={paused}
              onChange={setPaused}
              checkedChildren="暂停"
              unCheckedChildren="实时"
            />
            <Button icon={<ReloadOutlined />} onClick={() => { loadHistory().then(() => connectSSE()) }}>
              刷新
            </Button>
            <Button icon={<ClearOutlined />} onClick={() => { setLogs([]); logIdSetRef.current.clear() }}>
              清空
            </Button>
          </Space>
        </div>
      </Card>

      <div
        ref={containerRef}
        style={{
          background: '#1e1e1e',
          color: '#d4d4d4',
          fontFamily: 'Consolas, Monaco, monospace',
          fontSize: 12,
          lineHeight: 1.8,
          padding: 16,
          borderRadius: 8,
          height: 'calc(100vh - 280px)',
          overflowY: 'auto',
          minHeight: 400,
        }}
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin tip="加载日志中..." />
          </div>
        ) : filteredLogs.length === 0 ? (
          <Empty description="暂无日志" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          filteredLogs.map((log) => (
            <div key={log.id} style={{ borderBottom: '1px solid #333', padding: '2px 0' }}>
              <span style={{ color: '#888' }}>{log.time}</span>
              <span style={{
                color: log.level === 'ERROR' ? '#f44' : log.level === 'WARNING' ? '#fa0' :
                       log.level === 'SUCCESS' ? '#4f4' : '#6cf',
                marginLeft: 8,
                fontWeight: 'bold',
              }}>
                [{log.level}]
              </span>
              <span style={{ color: '#888', marginLeft: 8 }}>[{log.module}]</span>
              <span style={{ marginLeft: 8 }}>{log.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
