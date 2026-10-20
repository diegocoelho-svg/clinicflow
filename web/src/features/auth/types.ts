export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
}

export interface Credentials {
  username: string;
  password: string;
}
export interface Registration extends Credentials {
  email: string;
  first_name: string;
  last_name: string;
}
export interface Session {
  token: string;
  user: User;
}
