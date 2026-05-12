import React from 'react'
import { Card, Typography, Result, Button } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/auth'
import { LockOutlined, RobotOutlined } from '@ant-design/icons'

const { Title, Text } = Typography

export default function SettingsPage() {
  const navigate = useNavigate()
  const role = useAuthStore(s => s.role)

  return (
    <div>
      <Title level={4}>系统设置</Title>
      <Card style={{ marginBottom: 16 }}>
        <Result
          icon={<LockOutlined />}
          title="Cookie 管理已迁移"
          subTitle="Cookie 管理已移至「个人中心 → Cookie 管理」"
          extra={
            <Button type="primary" onClick={() => navigate('/user-center')}>
              前往个人中心
            </Button>
          }
        />
      </Card>
      {role === 'admin' && (
        <Card>
          <Result
            icon={<RobotOutlined />}
            title="模型配置已迁移"
            subTitle="模型配置已移至「管理后台 → 模型配置」"
            extra={
              <Button type="primary" onClick={() => navigate('/admin')}>
                前往管理后台
              </Button>
            }
          />
        </Card>
      )}
    </div>
  )
}
