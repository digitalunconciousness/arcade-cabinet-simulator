// license:CC0-1.0
#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D u_texture;
varying vec2 v_uv;

void main() {
  vec4 base = texture2D(u_texture, v_uv);
  gl_FragColor = vec4(base.rgb * 0.55, 1.0);
}
