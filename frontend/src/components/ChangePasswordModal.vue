<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { api } from '@/api'

// G02 自助改密：开关由父组件 v-model:open 控制；成功后父组件负责强制退出。
const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ changed: [] }>()

const formRef = ref<{ validate: () => Promise<unknown>; resetFields: () => void }>()
const saving = ref(false)
const form = reactive({ current_password: '', new_password: '', confirm_password: '' })

// 校验规则：新密码对齐服务端 12 位下限；确认密码需与新密码一致。
const rules = {
  current_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, min: 12, max: 128, message: '新密码长度须为 12–128 个字符', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule: unknown, value: string) =>
        value === form.new_password ? Promise.resolve() : Promise.reject(new Error('两次输入的新密码不一致')),
      trigger: 'blur',
    },
  ],
}

// 每次打开清空上次输入，避免残留明文密码。
watch(open, (next) => {
  if (next) {
    form.current_password = ''
    form.new_password = ''
    form.confirm_password = ''
    formRef.value?.resetFields()
  }
})

// 提交成功后服务端已撤销全部会话并提升 auth_version，由父组件引导重新登录。
async function submitChange(): Promise<void> {
  try { await formRef.value?.validate() } catch { return }
  saving.value = true
  try {
    await api('/auth/me/password', {
      method: 'POST',
      body: JSON.stringify({ current_password: form.current_password, new_password: form.new_password }),
    })
    message.success('密码已修改，请使用新密码重新登录')
    open.value = false
    emit('changed')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '修改密码失败')
  } finally { saving.value = false }
}
</script>

<template>
  <a-modal v-model:open="open" title="修改密码" ok-text="确认修改" cancel-text="取消" :confirm-loading="saving" @ok="submitChange">
    <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
      <a-form-item label="当前密码" name="current_password">
        <a-input-password v-model:value="form.current_password" autocomplete="current-password" :maxlength="128" />
      </a-form-item>
      <a-form-item label="新密码（至少 12 位）" name="new_password">
        <a-input-password v-model:value="form.new_password" autocomplete="new-password" :maxlength="128" />
      </a-form-item>
      <a-form-item label="确认新密码" name="confirm_password">
        <a-input-password v-model:value="form.confirm_password" autocomplete="new-password" :maxlength="128" />
      </a-form-item>
      <a-alert type="warning" show-icon message="修改成功后所有登录会话将被撤销（包括当前设备），需使用新密码重新登录。" />
    </a-form>
  </a-modal>
</template>
