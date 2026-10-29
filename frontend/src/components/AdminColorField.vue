<script setup lang="ts">
// ant-design-vue 4.2.6 尚未导出 ColorPicker，用输入框承接十六进制主色。
const model = defineModel<string>({ default: '#18181B' })

function onHexChange(value: string): void {
  if (/^#[\da-f]{6}$/i.test(value)) model.value = value
}
</script>

<template>
  <a-space>
    <input
      :value="model"
      type="color"
      aria-label="选择颜色"
      class="h-8 w-8 cursor-pointer border-0 bg-transparent p-0"
      @input="onHexChange(($event.target as HTMLInputElement).value)"
    />
    <a-input :value="model" :maxlength="7" class="w-28" @update:value="onHexChange" />
  </a-space>
</template>
