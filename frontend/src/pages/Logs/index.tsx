import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Card, Typography, Space, Button, Tag, Select, Badge, Switch, Empty } from 'antd'
import { PauseCircleOutlined, PlayCircleOutlined, ClearOutlined, ReloadOutlined } from '@ant-design/icons'

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
  const containerRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)
  const autoScrollRef = useRef(true)

  const connectSSE = useCallback(() => {
    if (esRef.current) esRef.current.close()

    const es = new EventSource('/api/logs/stream')
    esRef.current = es

    es.onopen = () => setConnected(true)
    es.onerror = () => {
      setConnected(false)
      setTimeout(connectSSE, 3000)
    }
    es.onmessage = (e) => {
      if (paused) return
      try {
        const entry = JSON.parse(e.data)
        setLogs(prev => {
          const next = [...prev, entry]
          if (next.length > 500) return next.slice(-500)
          return next
        })
      } catch {}
    }
  }, [paused])

  useEffect(() => {
    if (!paused) connectSSE()
    return () => { esRef.current?.close() }
  }, [paused, connectSSE])

  useEffect(() => {
    if (autoScrollRef.current && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [logs])

  const filteredLogs = levelFilter
    ? logs.filter(l => l.level === levelFilter)
    : logs

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <Title level={4}>运行日志</Title>
      <Space style={{ marginBottom: 16 }}>
        <Badge status={connected ? 'success' : 'error'} text={connected ? '已连接' : '未连接'} />
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
        <Button icon={<ClearOutlined />} onClick={() => setLogs([])}>清空</Button>
      </Space>

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
        {filteredLogs.length === 0 ? (
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
