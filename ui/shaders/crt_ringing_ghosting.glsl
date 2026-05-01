// license:CC0-1.0
#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D u_texture;
varying vec2 v_uv;

void main() {
  vec4 base = texture2D(u_texture, v_uv);
  vec4 ghost = texture2D(u_texture, vec2(v_uv.x - 0.01, v_uv.y));
  gl_FragColor = vec4(base.rgb * 0.8 + ghost.rgb * 0.2, 1.0);
}
