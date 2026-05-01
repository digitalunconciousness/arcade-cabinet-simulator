// license:CC0-1.0
#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D u_texture;
varying vec2 v_uv;

void main() {
  vec2 off = vec2(0.002, 0.002);
  vec4 c0 = texture2D(u_texture, v_uv);
  vec4 c1 = texture2D(u_texture, v_uv + off);
  vec4 c2 = texture2D(u_texture, v_uv - off);
  gl_FragColor = (c0 + c1 + c2) / 3.0;
}
