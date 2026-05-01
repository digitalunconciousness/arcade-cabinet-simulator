// license:CC0-1.0
#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D u_texture;
varying vec2 v_uv;

void main() {
  float center = 0.5;
  float y = mix(center, v_uv.y, 0.04);
  vec4 base = texture2D(u_texture, vec2(v_uv.x, y));
  float line = smoothstep(0.49, 0.5, v_uv.y) * (1.0 - smoothstep(0.5, 0.51, v_uv.y));
  gl_FragColor = vec4(base.rgb + vec3(line * 0.8), 1.0);
}
