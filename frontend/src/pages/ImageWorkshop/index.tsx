import React, { useState } from 'react'
import { Card, Upload, Button, Select, Space, Typography, Row, Col, message, Image, Spin, Tabs, Radio } from 'antd'
import { UploadOutlined, ScissorOutlined, PictureOutlined, BulbOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title, Text } = Typography

// ── 传统降重 Tab ─────────────────────────────────────────────────────────────

function AntiDuplicateTab() {
  const [preset, setPreset] = useState('medium')
  const [images, setImages] = useState<any[]>([])
  const [processed, setProcessed] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const onUpload = (file: any) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      setImages(prev => [...prev, { file, preview: e.target?.result }])
    }
    reader.readAsDataURL(file)
    return false
  }

  const onProcess = async () => {
    if (!images.length) return message.warning('请先上传图片')
    setLoading(true)
    try {
      const base64List = images.map(img => img.preview)
      const r = await client.post('/images/process', { images: base64List, preset })
      if (r.data.success) {
        setProcessed(r.data.data.filter((d: any) => d.success).map((d: any) => d.image))
        message.success(`处理完成: ${r.data.data.filter((d: any) => d.success).length}/${images.length}`)
      }
    } catch {
      message.error('处理失败')
    }
    setLoading(false)
  }

  return (
    <>
      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Upload beforeUpload={onUpload} multiple accept="image/*" showUploadList={false}>
            <Button icon={<UploadOutlined />}>上传图片</Button>
          </Upload>
          <Select value={preset} onChange={setPreset} style={{ width: 120 }}
            options={[
              { value: 'light', label: '轻度处理' },
              { value: 'medium', label: '中度处理' },
              { value: 'heavy', label: '重度处理' },
            ]} />
          <Button type="primary" icon={<ScissorOutlined />} loading={loading} onClick={onProcess}>
            开始处理
          </Button>
          <Button onClick={() => { setImages([]); setProcessed([]) }}>清空</Button>
        </Space>
      </Card>
      <Row gutter={16}>
        <Col span={12}>
          <Card title={`原图 (${images.length})`} size="small">
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {images.map((img, i) => (
                <Image key={i} src={img.preview} width={120} height={120}
                  style={{ objectFit: 'cover', borderRadius: 4 }} />
              ))}
              {!images.length && <div style={{ color: '#999', padding: 40 }}>点击上方按钮上传图片</div>}
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card title={`处理后 (${processed.length})`} size="small">
            <Spin spinning={loading}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {processed.map((img, i) => (
                  <Image key={i} src={img} width={120} height={120}
                    style={{ objectFit: 'cover', borderRadius: 4 }} />
                ))}
                {!processed.length && !loading && <div style={{ color: '#999', padding: 40 }}>处理后的图片将显示在这里</div>}
              </div>
            </Spin>
          </Card>
        </Col>
      </Row>
    </>
  )
}

// ── AI 风格重绘 Tab ─────────────────────────────────────────────────────────

const STYLE_OPTIONS = [
  { value: '漫画风', label: '漫画风', color: '#ff4757', desc: '边缘增强 + 颜色量化，漫画效果' },
  { value: '油画风', label: '油画风', color: '#e17055', desc: '双边滤波 + 形态学处理，油画笔触' },
  { value: '水彩风', label: '水彩风', color: '#00b894', desc: '模糊混合 + 饱和度提升，水彩画效果' },
  { value: '复古风', label: '复古风', color: '#6c5ce7', desc: '棕褐色调 + 暗角 + 噪点，老照片风格' },
  { value: '清新风', label: '清新风', color: '#0984e3', desc: '提亮 + 暖色调，清新明亮风格' },
  { value: '赛博朋克', label: '赛博朋克', color: '#e84393', desc: '色相偏移 + 边缘高亮，霓虹灯效果' },
]

function AIRedrawTab() {
  const [style, setStyle] = useState('清新风')
  const [images, setImages] = useState<any[]>([])
  const [processed, setProcessed] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const onUpload = (file: any) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      setImages(prev => [...prev, { file, preview: e.target?.result }])
    }
    reader.readAsDataURL(file)
    return false
  }

  const onRedraw = async () => {
    if (!images.length) return message.warning('请先上传图片')
    setLoading(true)
    try {
      const base64List = images.map(img => img.preview)
      const r = await client.post('/images/ai-redraw', { images: base64List, style })
      if (r.data.success) {
        setProcessed(r.data.data.filter((d: any) => d.success).map((d: any) => d.image))
        message.success(r.data.message || '风格化处理完成')
      } else {
        message.error(r.data.message || '处理失败')
      }
    } catch {
      message.error('处理失败')
    }
    setLoading(false)
  }

  return (
    <>
      <Card style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Text strong>选择风格：</Text>
            <div style={{ marginTop: 8 }}>
              <Radio.Group value={style} onChange={e => setStyle(e.target.value)}>
                <Space wrap>
                  {STYLE_OPTIONS.map(s => (
                    <Radio.Button key={s.value} value={s.value}
                      style={{ borderColor: style === s.value ? s.color : undefined }}>
                      {s.label}
                    </Radio.Button>
                  ))}
                </Space>
              </Radio.Group>
            </div>
            <Text type="secondary" style={{ marginTop: 4, display: 'block' }}>
              {STYLE_OPTIONS.find(s => s.value === style)?.desc}
            </Text>
          </div>
          <Space>
            <Upload beforeUpload={onUpload} multiple accept="image/*" showUploadList={false}>
              <Button icon={<UploadOutlined />}>上传图片</Button>
            </Upload>
            <Button type="primary" icon={<BulbOutlined />} loading={loading} onClick={onRedraw}>
              开始风格化
            </Button>
            <Button onClick={() => { setImages([]); setProcessed([]) }}>清空</Button>
          </Space>
        </Space>
      </Card>
      <Row gutter={16}>
        <Col span={12}>
          <Card title={`原图 (${images.length})`} size="small">
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {images.map((img, i) => (
                <Image key={i} src={img.preview} width={120} height={120}
                  style={{ objectFit: 'cover', borderRadius: 4 }} />
              ))}
              {!images.length && <div style={{ color: '#999', padding: 40 }}>上传图片后选择风格进行重绘</div>}
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card title={`风格化后 (${processed.length})`} size="small">
            <Spin spinning={loading}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {processed.map((img, i) => (
                  <Image key={i} src={img} width={120} height={120}
                    style={{ objectFit: 'cover', borderRadius: 4 }} />
                ))}
                {!processed.length && !loading && <div style={{ color: '#999', padding: 40 }}>风格化结果将显示在这里</div>}
              </div>
            </Spin>
          </Card>
        </Col>
      </Row>
    </>
  )
}

// ── 主页面 ──────────────────────────────────────────────────────────────────

export default function ImageWorkshopPage() {
  return (
    <div>
      <Title level={4}>图片工作台</Title>
      <Tabs items={[
        {
          key: 'anti-duplicate',
          label: <span><ScissorOutlined /> 传统降重</span>,
          children: <AntiDuplicateTab />,
        },
        {
          key: 'ai-redraw',
          label: <span><PictureOutlined /> AI 风格重绘</span>,
          children: <AIRedrawTab />,
        },
      ]} />
    </div>
  )
}
