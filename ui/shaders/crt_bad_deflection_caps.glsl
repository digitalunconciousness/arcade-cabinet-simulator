// license:CC0-1.0
#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D u_texture;
uniform float u_time;
varying vec2 v_uv;

void main() {
  float wave = sin((v_uv.y * 20.0) + (u_time * 2.5)) * 0.01;
  vec2 uv = vec2(v_uv.x + wave, v_uv.y);
  gl_FragColor = texture2D(u_texture, uv);
}
