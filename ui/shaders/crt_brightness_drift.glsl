// license:CC0-1.0
#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D u_texture;
uniform float u_time;
varying vec2 v_uv;

void main() {
  float drift = 0.85 + 0.15 * sin(u_time * 0.9);
  vec4 base = texture2D(u_texture, v_uv);
  gl_FragColor = vec4(base.rgb * drift, 1.0);
}
