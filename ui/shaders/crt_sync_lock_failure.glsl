// license:CC0-1.0
#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D u_texture;
uniform float u_time;
varying vec2 v_uv;

void main() {
  float roll = fract(v_uv.y + (u_time * 0.1));
  gl_FragColor = texture2D(u_texture, vec2(v_uv.x, roll));
}
