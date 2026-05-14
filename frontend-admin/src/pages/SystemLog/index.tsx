import React, { useState, useEffect, useRef } from 'react'
import { Card, Typography, Space, Button, Tag, Select, Switch, Empty, Spin } from 'antd'
import { ReloadOutlined, PauseCircleOutlined, PlayCircleOutlined, ClearOutlined } from '@ant-design/icons'
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
  INFO: 'blue', WARNING: 'orange', ERROR: 'red', SUCCESS: 'green', DEBUG: 'default'
}

export default function SystemLogPage() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [paused, setPaused] = useState(false)
  const [levelFilter, setLevelFilter] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const containerRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)
  const logIdSetRef = useRef(new Set<number>())

  const loadHistory = async () => {
    setLoading(true)
    try {
      const r = await client.get('/logs', { params: { limit: 200 } })
      if (r.data.success) {
        setLogs(r.data.data)
        logIdSetRef.current = new Set(r.data.data.map((l: LogEntry) => l.id))
      }
    } catch {}
    setLoading(false)
  }

  useEffect(() => { loadHistory() }, [])

  // SSE 实时日志
  useEffect(() => {
    const es = new EventSource('/api/logs/stream')
    esRef.current = es
    es.onmessage = (e) => {
      if (paused) return
      const log = JSON.parse(e.data)
      setLogs(prev => [log, ...prev.filter(l => l.id !== log.id)].slice(0, 500))
    }
    es.onerror = () => {
      setTimeout(() => { if (es.readyState === EventSource.CLOSED) es.close() }, 3000)
    }
    return () => es.close()
  }, [paused])

  const filteredLogs = levelFilter ? logs.filter(l => l.level === levelFilter) : logs

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>📋 系统日志</Title>
        <Space>
          <Switch checkedChildren={<PauseCircleOutlined />} unCheckedChildren={<PlayCircleOutlined />} checked={paused} onChange={setPaused} />
          <Select value={levelFilter} onChange={setLevelFilter} allowClear placeholder="日志级别" style={{ width: 120 }}
            options={Object.keys(LEVEL_COLORS).map(l => ({ label: l, value: l }))} />
          <Button icon={<ReloadOutlined />} onClick={loadHistory}>刷新</Button>
          <Button icon={<ClearOutlined />} onClick={() => setLogs([])}>清屏</Button>
        </Space>
      </div>
      <Card style={{ minHeight: 500 }}>
        {loading ? <Spin /> : filteredLogs.length === 0 ? <Empty /> : (
          <div ref={containerRef} style={{ maxHeight: 500, overflow: 'auto' }}>
            {filteredLogs.map(log => (
              <div key={log.id} style={{ padding: '8px 12px', borderBottom: '1px solid #f0f0f0', fontFamily: 'monospace', fontSize: 13 }}>
                <Space size="middle">
                  <Text type="secondary" style={{ fontSize: 12 }}>{log.time}</Text>
                  <Tag color={LEVEL_COLORS[log.level] || 'default'}>{log.level}</Tag>
                  <Text>{log.message}</Text>
                  {log.module && <Text type="secondary">{log.module}.{log.function}</Text>}
                </Space>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
