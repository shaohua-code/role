<script setup lang="ts">
import { watch } from 'vue'
import { SearchOutlined } from '../../app/icons'

const model = defineModel<string>({ default: '' })

const props = withDefaults(defineProps<{
  placeholder?: string
  /** 清空输入时是否触发 search（服务端筛选页需要刷新列表） */
  submitOnClear?: boolean
}>(), {
  placeholder: '搜索',
  submitOnClear: true,
})

const emit = defineEmits<{
  search: [query: string]
}>()

// 回车提交关键词，避免每键入一字就请求接口
function submitSearch(): void {
  emit('search', model.value.trim())
}

// 点击清除按钮时补一次查询（antd allow-clear 不会自动触发 search）
watch(model, (next, prev) => {
  if (next === '' && prev && props.submitOnClear) {
    emit('search', '')
  }
})
</script>

<template>
  <a-input
    v-model:value="model"
    class="admin-search-field"
    :placeholder="placeholder"
    allow-clear
    @press-enter="submitSearch"
  >
    <template #prefix>
      <SearchOutlined class="text-sm text-slate-400" />
    </template>
  </a-input>
</template>
