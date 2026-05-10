import React, { useState } from 'react'
import { Card, Upload, Button, Select, Space, Typography, Row, Col, message, Image, Spin } from 'antd'
import { UploadOutlined, ScissorOutlined } from '@ant-design/icons'
import client from '../../api/client'

const { Title } = Typography

export default function ImageWorkshopPage() {
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
    } catch (e: any) {
      message.error('处理失败')
    }
    setLoading(false)
  }

  return (
    <div>
      <Title level={4}>图片工作台</Title>
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
    </div>
  )
}
