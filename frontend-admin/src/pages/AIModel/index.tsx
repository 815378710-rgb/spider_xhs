import React, { useState, useEffect, useMemo } from 'react'
import { Card, Typography, Form, Input, Select, Button, message, Space, Alert, AutoComplete, Tag } from 'antd'
import { SaveOutlined, ApiOutlined, ThunderboltOutlined, ReloadOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text } = Typography

// ── AI 厂商元数据（前端内置，即时响应） ──────────────────────────────────
interface ProviderMeta {
  label: string
  base_url: string
  models: string[]
}

const PROVIDERS: Record<string, ProviderMeta> = {
  deepseek: {
    label: 'DeepSeek',
    base_url: 'https://api.deepseek.com/v1',
    models: ['deepseek-chat', 'deepseek-reasoner', 'deepseek-v3'],
  },
  qwen: {
    label: '通义千问 (阿里)',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: ['qwen-turbo', 'qwen-plus', 'qwen-max', 'qwen-long', 'qwen3-235b-a22b'],
  },
  openai: {
    label: 'OpenAI',
    base_url: 'https://api.openai.com/v1',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1', 'o3-mini'],
  },
  azure: {
    label: 'Azure OpenAI',
    base_url: 'https://YOUR_RESOURCE.openai.azure.com',
    models: [],
  },
  zhipu: {
    label: '智谱AI (GLM)',
    base_url: 'https://open.bigmodel.cn/api/paas/v4',
    models: ['glm-4-plus', 'glm-4', 'glm-4-flash', 'glm-4-air', 'glm-4-airx'],
  },
  moonshot: {
    label: 'Moonshot (Kimi)',
    base_url: 'https://api.moonshot.cn/v1',
    models: ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'],
  },
  qianfan: {
    label: '百度千帆',
    base_url: 'https://qianfan.baidubce.com/v2',
    models: ['ernie-4.0-turbo-128k', 'ernie-3.5-128k', 'ernie-speed-128k'],
  },
  doubao: {
    label: '豆包 (字节)',
    base_url: 'https://ark.cn-beijing.volces.com/api/v3',
    models: ['doubao-pro-128k', 'doubao-lite-128k', 'doubao-pro-32k'],
  },
  siliconflow: {
    label: '硅基流动 (SiliconFlow)',
    base_url: 'https://api.siliconflow.cn/v1',
    models: ['deepseek-ai/DeepSeek-V3', 'Qwen/Qwen2.5-72B-Instruct', 'Pro/Llama-3.3-70B-Instruct'],
  },
  ollama: {
    label: 'Ollama (本地部署)',
    base_url: 'http://localhost:11434/v1',
    models: [],
  },
  mimo: {
    label: 'MiMo',
    base_url: '',
    models: [],
  },
  custom: {
    label: '自定义',
    base_url: '',
    models: [],
  },
}

const PROVIDER_OPTIONS = Object.entries(PROVIDERS).map(([value, meta]) => ({
  value,
  label: meta.label,
}))

export default function AIModelPage() {
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [liveModels, setLiveModels] = useState<string[]>([])
  const [form] = Form.useForm()

  const selectedProvider: string = Form.useWatch('provider', form) || ''

  // 当前厂商的内置模型列表
  const builtinModels = useMemo(() => {
    return PROVIDERS[selectedProvider]?.models || []
  }, [selectedProvider])

  // 合并内置模型 + 测试获取的在线模型（去重）
  const allModelOptions = useMemo(() => {
    const merged = new Set([...builtinModels, ...liveModels])
    return Array.from(merged).map((m) => ({ value: m, label: m }))
  }, [builtinModels, liveModels])

  // 是否有内置模型可选
  const hasBuiltinModels = builtinModels.length > 0

  // 加载当前配置
  const loadConfig = async () => {
    setLoading(true)
    try {
      const r = await client.get('/config/llm')
      if (r.data.success) {
        const d = r.data.data
        form.setFieldsValue({
          provider: d.provider || 'deepseek',
          api_key: d.api_key || '',
          model: d.model || '',
          base_url: d.base_url || '',
        })
        // 如果当前 provider 有 base_url 但字段为空，自动填充
        if (!d.base_url && d.provider && PROVIDERS[d.provider]?.base_url) {
          form.setFieldValue('base_url', PROVIDERS[d.provider].base_url)
        }
      }
    } catch (e: any) {
      message.error('加载失败：' + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadConfig()
  }, [])

  // 切换厂商时自动填充 base_url 和清空模型
  const handleProviderChange = (provider: string) => {
    const meta = PROVIDERS[provider]
    if (meta) {
      form.setFieldValue('base_url', meta.base_url || '')
      // 如果只有1个内置模型，自动选中
      if (meta.models.length === 1) {
        form.setFieldValue('model', meta.models[0])
      } else {
        form.setFieldValue('model', '')
      }
    }
    setLiveModels([])
    setTestResult(null)
  }

  // 保存配置
  const onFinish = async (values: any) => {
    try {
      const r = await client.post('/config/llm', values)
      if (r.data.success) {
        message.success('LLM 配置已保存')
      } else {
        message.error('保存失败：' + r.data.message)
      }
    } catch (e: any) {
      message.error('保存失败：' + (e.response?.data?.detail || e.message))
    }
  }

  // 测试连接
  const testConnection = async () => {
    const values = form.getFieldsValue()
    if (!values.api_key) {
      message.warning('请先填写 API Key')
      return
    }
    if (!values.base_url && !values.provider) {
      message.warning('请先选择 AI 提供商或填写 Base URL')
      return
    }
    setTesting(true)
    setTestResult(null)
    try {
      const r = await client.post('/config/llm/test', values)
      if (r.data.success) {
        setTestResult({ success: true, message: r.data.message })
        const models: string[] = r.data.data?.models || []
        if (models.length > 0) {
          setLiveModels(models)
          // 如果线上返回了模型列表且当前模型为空，自动选第一个
          if (!values.model && models.length > 0) {
            form.setFieldValue('model', models[0])
          }
          message.success(`连接成功！在线获取到 ${models.length} 个模型`)
        } else {
          message.success('连接成功！')
        }
      } else {
        setTestResult({ success: false, message: r.data.message })
        message.error('连接失败：' + r.data.message)
      }
    } catch (e: any) {
      const errMsg = e.response?.data?.detail || e.response?.data?.message || e.message
      setTestResult({ success: false, message: errMsg })
      message.error('连接失败：' + errMsg)
    } finally {
      setTesting(false)
    }
  }

  // 获取在线模型列表
  const fetchLiveModels = async () => {
    const values = form.getFieldsValue()
    if (!values.api_key) {
      message.warning('请先填写 API Key')
      return
    }
    setTesting(true)
    try {
      const r = await client.post('/config/llm/test', values)
      if (r.data.success) {
        const models: string[] = r.data.data?.models || []
        setLiveModels(models)
        if (models.length > 0) {
          message.success(`获取到 ${models.length} 个在线模型`)
        }
      } else {
        message.warning('获取模型列表失败：' + r.data.message)
      }
    } catch (e: any) {
      message.warning('获取失败，请先测试连接')
    } finally {
      setTesting(false)
    }
  }

  return (
    <div style={{ padding: 24 }}>
      <Title level={3} style={{ marginBottom: 24 }}>
        🤖 AI模型配置
      </Title>
      <Card style={{ maxWidth: 680 }}>
        <Alert
          message='配置 AI 模型后，系统将使用此模型进行内容改写、选题推荐、Agent 辩论等功能'
          type='info'
          showIcon
          style={{ marginBottom: 24 }}
        />

        <Form form={form} onFinish={onFinish} layout='vertical' initialValues={{ provider: 'deepseek' }}>
          {/* ── 厂商选择 ── */}
          <Form.Item name='provider' label='AI 提供商' rules={[{ required: true, message: '请选择 AI 提供商' }]}>
            <Select
              showSearch
              placeholder='选择 AI 提供商...'
              options={PROVIDER_OPTIONS}
              onChange={handleProviderChange}
              optionFilterProp='label'
            />
          </Form.Item>

          {/* ── API Key ── */}
          <Form.Item name='api_key' label='API Key' rules={[{ required: true, message: '请输入 API Key' }]}>
            <Input.Password placeholder='sk-... 或你的 API Key' visibilityToggle />
          </Form.Item>

          {/* ── 模型选择 ── */}
          <Form.Item
            name='model'
            label={
              <Space>
                模型名称
                {hasBuiltinModels && (
                  <Tag color='blue' style={{ fontSize: 11 }}>
                    {builtinModels.length} 个内置
                  </Tag>
                )}
                {liveModels.length > 0 && (
                  <Tag color='green' style={{ fontSize: 11 }}>
                    +{liveModels.length} 在线
                  </Tag>
                )}
              </Space>
            }
            rules={[{ required: true, message: '请输入或选择模型名称' }]}
          >
            {hasBuiltinModels || liveModels.length > 0 ? (
              <AutoComplete
                placeholder={
                  selectedProvider
                    ? `选择 ${PROVIDERS[selectedProvider]?.label} 模型...`
                    : '输入或搜索模型名称...'
                }
                options={allModelOptions}
                filterOption={(inputValue, option) =>
                  (option?.value ?? '').toLowerCase().includes(inputValue.toLowerCase())
                }
                allowClear
              >
                <Input />
              </AutoComplete>
            ) : (
              <Input
                placeholder={
                  selectedProvider === 'custom'
                    ? '输入自定义模型名称...'
                    : selectedProvider === 'ollama'
                    ? '如 llama3, qwen2.5...'
                    : '输入模型名称...'
                }
              />
            )}
          </Form.Item>

          {/* ── Base URL ── */}
          <Form.Item
            name='base_url'
            label='Base URL'
            tooltip='OpenAI 兼容 API 的 base URL，选厂商标后自动填充'
          >
            <Input placeholder='https://api.deepseek.com/v1' />
          </Form.Item>

          {/* ── 操作按钮 ── */}
          <Form.Item>
            <Space wrap>
              <Button type='primary' htmlType='submit' icon={<SaveOutlined />} loading={loading}>
                保存配置
              </Button>
              <Button icon={<ThunderboltOutlined />} onClick={testConnection} loading={testing}>
                测试连接
              </Button>
              <Button icon={<ApiOutlined />} onClick={fetchLiveModels} loading={testing} disabled={!form.getFieldValue('api_key')}>
                拉取在线模型
              </Button>
              <Button icon={<ReloadOutlined />} onClick={loadConfig}>
                重新加载
              </Button>
            </Space>
          </Form.Item>
        </Form>

        {/* ── 测试结果提示 ── */}
        {testResult && (
          <Alert
            type={testResult.success ? 'success' : 'error'}
            message={testResult.success ? '连接成功' : '连接失败'}
            description={testResult.message}
            showIcon
            closable
            onClose={() => setTestResult(null)}
            style={{ marginTop: 8 }}
          />
        )}

        {/* ── 厂商速查表 ── */}
        <div
          style={{
            marginTop: 20,
            padding: 12,
            background: '#fafafa',
            borderRadius: 8,
            border: '1px solid #f0f0f0',
          }}
        >
          <Text type='secondary' strong style={{ fontSize: 12 }}>
            支持厂商一览
          </Text>
          <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {Object.entries(PROVIDERS).map(([key, meta]) => (
              <Tag
                key={key}
                color={selectedProvider === key ? 'blue' : 'default'}
                style={{ cursor: 'pointer' }}
                onClick={() => {
                  form.setFieldValue('provider', key)
                  handleProviderChange(key)
                }}
              >
                {meta.label}
              </Tag>
            ))}
          </div>
        </div>
      </Card>
    </div>
  )
}
