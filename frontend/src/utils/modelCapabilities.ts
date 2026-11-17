// 模型能力标准标签（与后端 schemas/models.py MODEL_CAPABILITIES 同源）；
// 网关与业务端按此解释模型特性：是否深度思考、是否有思考过程、是否支持工具调用等。
export interface ModelCapabilityOption { value: string; label: string; hint: string }

export const MODEL_CAPABILITY_OPTIONS: ModelCapabilityOption[] = [
  { value: 'chat', label: '对话', hint: '常规对话补全' },
  { value: 'reasoning', label: '深度思考', hint: '支持思考模式（推理模型）' },
  { value: 'thinking_output', label: '思考过程输出', hint: '返回可见的思维链内容' },
  { value: 'tool_calls', label: '工具调用', hint: 'Function Calling / Agent 工具' },
  { value: 'json_output', label: 'JSON 输出', hint: 'JSON 结构化输出' },
  { value: 'vision', label: '视觉理解', hint: '支持图片输入' },
  { value: 'embedding', label: '向量嵌入', hint: 'Embedding 向量化模型' },
]

// 仅 formatCapabilities 内部使用；外部消费方请用 OPTIONS / formatCapabilities。
const MODEL_CAPABILITY_LABELS: Record<string, string> = Object.fromEntries(
  MODEL_CAPABILITY_OPTIONS.map(option => [option.value, option.label]),
)

// 渲染用：标签转中文，未知标签原样回显（历史数据兜底）。
export function formatCapabilities(capabilities: string[]): string {
  if (!capabilities?.length) return '—'
  return capabilities.map(code => MODEL_CAPABILITY_LABELS[code] ?? code).join('、')
}
