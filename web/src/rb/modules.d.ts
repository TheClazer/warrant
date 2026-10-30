declare module '*.jsx' {
  const Component: import('react').ComponentType<any>
  export default Component
}

declare module '*.svg' {
  const url: string
  export default url
}
